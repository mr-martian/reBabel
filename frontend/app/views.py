from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from app import models
from functools import wraps
import json
from requests import post

def json2json(fn):
    @wraps(fn)
    def _fn(request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            resp = fn(data, *args, **kwargs)
            if isinstance(resp, tuple):
                d, c = resp
                h = JsonResponse(d)
                h.status_code = c
                return h
            return JsonResponse(resp)
        except Exception as e:
            print(e)
            h = JsonResponse({'error': 'something went wrong'})
            h.status_code = 500
            return h
    return _fn

def check_project(fn):
    @login_required
    @wraps(fn)
    def _fn(request, projectid, **kwargs):
        p = get_object_or_404(models.Project, pk=projectid)
        a = None
        if p.owner != request.user:
            a = models.ProjectAccess.objects.filter(
                project=p, user=request.user).first()
            if a is None:
                raise PermissionDenied()
        return fn(request, p, a, **kwargs)
    return _fn

def home(request):
    return render(request, 'app/home.html')

@login_required
def projects(request):
    owned = models.Project.objects.filter(owner=request.user)
    access = models.ProjectAccess.objects.filter(user=request.user)
    return render(request, 'app/projects.html',
                  {'owned': owned, 'access': access})

@login_required
def profile(request):
    # TODO
    return redirect('app:projects')

@check_project
def view_project(request, project, access=None):
    types = []
    for typ, val in project.fields.items():
        if 'list' in val:
            types.append(typ)
    return render(request, 'app/view_project.html',
                  {'project': project, 'types': types})

API_URL = 'http://127.0.0.1:9000/' # TODO

@check_project
def list_types(request, project, access=None, unittype='document'):
    data = {
        'project': project.backend_id,
        'type': unittype,
        'tier': 'meta',
        'feature': 'active',
    }
    if 'list' in project.fields.get(unittype, {}):
        data.update(project.fields[unittype]['list'])
    req = post(API_URL+'listType', json=data)
    units = []
    if req.status_code == 200:
        units = req.json()['units']
    return render(request, 'app/list_units.html',
                  {'project': project, 'type': unittype, 'units': units})

@check_project
def create_unit(request, project, access=None, unittype='document'):
    data = {
        'project': project.backend_id,
        'type': unittype,
    }
    req = post(API_URL+'createUnit', json=data)
    if req.status_code == 200:
        return redirect('app:view_unit', projectid=project.id, unitid=req.json()['id'])
    # TODO
    return redirect('app:home')

@check_project
def view_unit(request, project, access=None, unitid=0):
    views = models.ProjectView.objects.filter(project=project, user=request.user)
    default = views.first()
    for v in views:
        if v.default:
            default = v
            break
    return render(request, 'app/edit.html',
                  {
                      'project': project,
                      'access': access,
                      'unit': unitid,
                      'views': views,
                      'default_view': default,
                  })

@check_project
@json2json
def get_unit(data, project, access=None):
    if 'item' not in data:
        return {'error': 'missing item id'}, 500
    body = {
        'project': project.backend_id,
        'item': int(data['item']),
    }
    req = post(API_URL+'get', json=body)
    return req.json(), req.status_code

@check_project
@json2json
def set_features(data, project, access=None):
    print(data)
    if 'item' not in data:
        return {'error': 'missing item id'}, 500
    if 'features' not in data:
        return {'error': 'missing feature list'}, 500
    # TODO: validate structure of data['features']
    if access:
        if access.write_fields is False:
            return {'error': 'writing not allowed'}, 403
        if isinstance(access.write_fields, list):
            for f in data['features']:
                # TODO: no way to distinguish features with the same
                # name but for different unit types
                if not any(a['tier'] == f['tier'] and a['feature'] == f['feature'] for a in access.write_fields):
                    return {'error': 'writing not allowed'}, 403
    username = access.user.username if access else project.owner.username
    req = post(API_URL+'setFeature',
               json={
                   'project': project.backend_id,
                   'item': data['item'],
                   'features': data['features'],
                   'user': username,
                   'confidence': data.get('confidence', 1),
               })
    return req.json(), req.status_code

@check_project
@json2json
def add_unit(data, project, access=None):
    if 'type' not in data:
        return {'error': 'missing item type'}, 500
    req = post(API_URL+'createUnit',
               json={
                   'project': project.backend_id,
                   'type': data['type'],
                   'user': access.user.username if access else project.owner.username,
               })
    resp = req.json()
    if 'parent' in data:
        post(API_URL+'setParent',
             json={
                 'project': project.backend_id,
                 'parent': data['parent'],
                 'child': resp['id'],
             })
    return resp

@check_project
@json2json
def modification_times(data, project, access=None):
    if 'ids' not in data:
        return {'error': 'missing id list'}, 500
    req = post(API_URL+'modificationTimes',
               json={'project': project.backend_id, 'ids': data['ids']})
    return req.json(), req.status_code
