from django.core.management.base import BaseCommand, CommandError
from app.models import Project, ProjectView, User
from app.views import API_URL, post

DATA = {
    'flex': {
        'fields': {
            "document": {
                "fields": [
                    {"tier": "meta", "feature": "active", "type": "bool"},
                    {"tier": "info", "feature": "title", "type": "str"},
                ],
                "list": {"tier": "info", "feature": "title"}
            },
            "sentence": {
                "fields": [
                    {"tier": "meta", "feature": "active", "type": "bool"},
                    {"tier": "meta", "feature": "parent", "type": "ref"},
                    {"tier": "transcription", "feature": "text", "type": "str"},
                    {"tier": "translation", "feature": "free", "type": "str"},
                ],
            },
            "word": {
                "fields": [
                    {"tier": "meta", "feature": "active", "type": "bool"},
                    {"tier": "meta", "feature": "parent", "type": "ref"},
                    {"tier": "transcription", "feature": "form", "type": "str"},
                    {"tier": "gloss", "feature": "primary", "type": "str"},
                    {"tier": "gloss", "feature": "secondary", "type": "str"},
                ],
            },
            "morpheme": {
                "fields": [
                    {"tier": "meta", "feature": "active", "type": "bool"},
                    {"tier": "meta", "feature": "parent", "type": "ref"},
                    {"tier": "transcription", "feature": "form", "type": "str"},
                    {
                        "tier": "lexicon",
                        "feature": "lexeme",
                        "type": "ref",
                        "reftype": "lexeme",
                    },
                ],
            },
            "lexeme": {
                "fields": [
                    {"tier": "meta", "feature": "active", "type": "bool"},
                    {"tier": "lexicon", "feature": "headword", "type": "str"},
                    {"tier": "lexicon", "feature": "stem", "type": "str"},
                    {"tier": "lexicon", "feature": "gloss", "type": "str"},
                    {"tier": "lexicon", "feature": "translation", "type": "str"},
                ],
            },
        },
        'view': {
            "document": {
                "features": True,
                "children": ["sentence"],
            },
            "sentence": {
                "features": True,
                "children": ["word"],
            },
            "word": {
                "features": True,
                "children": ["morpheme"],
            },
            "morpheme": {
                "features": True,
                "children": [],
            },
            "lexeme": {
                "features": True,
                "children": [],
            },
        }
    },
    'fieldmethods': {
        'fields': {
            "document": {
                "fields": [
                    {"tier": "meta", "feature": "active", "type": "bool"},
                    {"tier": "info", "feature": "title", "type": "str"},
                ],
                "list": {"tier": "info", "feature": "title"}
            },
            "sentence": {
                "fields": [
                    {"tier": "meta", "feature": "active", "type": "bool"},
                    {"tier": "meta", "feature": "parent", "type": "ref"},
                    {"tier": "elicitation", "feature": "prompt", "type": "str"},
                    {"tier": "elicitation", "feature": "response", "type": "str"},
                    {"tier": "elicitation", "feature": "notes", "type": "str"},
                ],
            },
            "word": {
                "fields": [
                    {"tier": "meta", "feature": "active", "type": "bool"},
                    {"tier": "meta", "feature": "parent", "type": "ref"},
                    {"tier": "text", "feature": "form", "type": "str"},
                    {"tier": "text", "feature": "gloss", "type": "str"},
                    {
                        "tier": "lexicon",
                        "feature": "lexeme",
                        "type": "ref",
                        "reftype": "lexeme",
                    },
                ],
            },
            "lexeme": {
                "fields": [
                    {"tier": "meta", "feature": "active", "type": "bool"},
                    {"tier": "lexicon", "feature": "lemma", "type": "str"},
                    {"tier": "lexicon", "feature": "translation", "type": "str"},
                ],
                "list": {"tier": "lexicon", "feature": "lemma"},
            },
        },
        'view': {
            "document": {
                "features": True,
                "children": ["sentence"],
            },
            "sentence": {
                "features": True,
                "children": ["word"],
            },
            "word": {
                "features": True,
                "children": [],
            },
            "lexeme": {
                "features": True,
                "children": [],
            },
        }
    },
}

class Command(BaseCommand):
    help = 'temporary script to generate a template project until I figure out how to make a proper project management interface'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str)
        parser.add_argument('projecttype', choices=DATA.keys())

    def handle(self, *args, **kwargs):
        u = User.objects.filter(username=kwargs['username']).first()
        if u is None:
            raise CommandError('User does not exist')
        proj = Project()
        proj.name = 'test project'
        proj.owner = u
        proj.fields = DATA[kwargs['projecttype']]['fields']
        proj.save()
        pv = ProjectView()
        pv.project = proj
        pv.user = u
        pv.data = DATA[kwargs['projecttype']]['view']
        pv.name = 'default view'
        pv.default = True
        pv.save()
        post(API_URL+'createProject', json={'project': proj.backend_id})
        for typ in proj.fields:
            post(API_URL+'createType', json={
                'project': proj.backend_id,
                'type': typ,
            })
            for f in proj.fields[typ]['fields']:
                if f['tier'] == 'meta' and f['feature'] == 'active':
                    continue
                post(API_URL+'createFeature', json={
                    'project': proj.backend_id,
                    'unittype': typ,
                    'tier': f['tier'],
                    'feature': f['feature'],
                    'valuetype': f['type'],
                })
