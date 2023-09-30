#!/usr/bin/env python3

from flask import Flask, request
import sqlite3 as sql # definitely not permanent
import os.path
import datetime
import functools
import json
from pathlib import Path

app = Flask('core')

# TODO - from cmdline or config file probably
PROJECT_DIR = os.path.join(
    os.path.dirname(os.path.realpath(__file__)),
    'projects/'
)
TIME_FORMAT = '%Y-%m-%d %H:%M:%S'

def now():
    return datetime.datetime.now().strftime(TIME_FORMAT)

def get_path(projectid, fname):
    return os.path.join(PROJECT_DIR, f'{projectid}/', fname)

NEW_DB_SCRIPT = '''
BEGIN;
-- TODO: created and modified as timestamp and active as bool
CREATE TABLE objects(id INTEGER PRIMARY KEY,
                     type TEXT,
                     created TEXT,
                     modified TEXT,
                     active INTEGER);
-- do these need primary keys of their own?
CREATE TABLE tiers(tier TEXT,
                   feature TEXT,
                   unittype TEXT,
                   valuetype TEXT);
CREATE TABLE int_features(id INTEGER,
                          feature TEXT,
                          value INTEGER,
                          user TEXT,
                          confidence INTEGER,
                          date TEXT,
                          probability REAL,
                          active INTEGER);
CREATE TABLE bool_features(id INTEGER,
                           feature TEXT,
                           value INTEGER,
                           user TEXT,
                           confidence INTEGER,
                           date TEXT,
                           probability REAL,
                           active INTEGER);
-- I wonder if there would be any benefit to having a separate table for
-- categorical features so that we could restrict the column size?
CREATE TABLE str_features(id INTEGER,
                          feature TEXT,
                          value TEXT,
                          user TEXT,
                          confidence INTEGER,
                          date TEXT,
                          probability REAL,
                          active INTEGER);
-- maybe we should drop reference features and just have links?
-- or is it beneficial to have an internal distiction between
-- parent-child relationships and others?
CREATE TABLE ref_features(id INTEGER,
                          feature TEXT,
                          value INTEGER,
                          user TEXT,
                          confidence INTEGER,
                          date TEXT,
                          probability REAL,
                          active INTEGER);
-- types are redundant with objects table, but it might simplify some
-- queries to duplicate that information (and it's not too much)
CREATE TABLE relations(parent INTEGER,
                       parent_type TEXT,
                       child INTEGER,
                       child_type TEXT,
                       isprimary INTEGER,
                       active INTEGER,
                       date TEXT);
COMMIT;
'''

def get_object(cur, objectid, features=None, reduced=False):
    # TODO: features is currently expected to be of the form
    # ['{tier}:{feat}', ...]
    # but we might want to further specify the unit type
    # and also whether reference features should be copied in
    # or whether they're referring to a unit that's near enough
    # that just the ID is sufficient
    cur.execute('SELECT type, modified FROM objects WHERE id = ? AND active = 1;', [objectid])
    result = cur.fetchone()
    if result is None:
        return None
    otype = result[0]
    modified = result[1]
    layers = {}
    feats_to_sort = set()
    where = ''
    if features:
        where = ' AND feature IN (%s)' % (', '.join(['?']*len(features)))
    for typ in ['int', 'bool', 'str', 'ref']:
        qr = f'SELECT feature, value, user, date, probability FROM {typ}_features WHERE id = ? AND active = 1' + where
        cur.execute(qr, [objectid] + (features or []))
        for f, v, u, d, p in cur.fetchall():
            tier, feat = f.split(':')
            if tier not in layers:
                layers[tier] = {}
            if u is None:
                if reduced:
                    continue
                feats_to_sort.add(f)
                if feat not in layers[tier]:
                    layers[tier][feat] = {
                        'user': None,
                        'choices': [{'value': v, 'probability': p}],
                        'date': d,
                    }
                else:
                    layers[tier][feat]['choices'].append({
                        'value': v,
                        'probability': p,
                    })
            else:
                val = v
                if typ == 'ref':
                    val = get_object(cur, v, features=features, reduced=reduced)
                elif typ == 'bool':
                    val = bool(v)
                if val is None:
                    continue
                layers[tier][feat] = {
                    'user': u,
                    'date': d,
                    'value': val,
                }
    children = {}
    qr = '''SELECT relations.child, relations.child_type, relations.isprimary
FROM relations
INNER JOIN objects ON relations.child = objects.id
WHERE relations.active = 1 AND objects.active = 1 AND relations.parent = ?'''
    cur.execute(qr, [objectid])
    for c, t, p in cur.fetchall():
        if t not in children:
            children[t] = []
        if p == 1:
            children[t].append(get_object(cur, c,
                                          features=features, reduced=reduced))
        else:
            children[t].append(c)
    # TODO: conflicts
    return {
        'type': otype,
        'id': objectid,
        'modified': modified,
        'layers': layers,
        'children': children,
    }

def get_unit_type(cur, uid):
    cur.execute('SELECT type FROM objects WHERE id = ?', (uid,))
    t = cur.fetchone()
    if t is not None:
        return t[0]
    return None

class Args:
    def __init__(self, required):
        self.now = now()
        self.error = None
        if request.json is None:
            self.error = ('invalid JSON', 400)
        else:
            self.data = request.json
            for check in required:
                val = request.json[check[0]]
                if check[0] not in request.json:
                    self.error = (f'{check[1]} is required', 400)
                    break
                if len(check) > 2:
                    typ = check[2]
                    if isinstance(typ, type):
                        if not isinstance(val, typ):
                            self.error = (f'invalid {check[1]}', 400)
                            break
                    elif typ == 'project':
                        pth = get_path(val, 'data.db')
                        if not os.path.exists(pth):
                            self.error = ('project does not exist', 404)
                            break
                        self.con = sql.connect(pth)
                        self.cur = self.con.cursor()
                    elif typ == 'unit':
                        if not isinstance(val, int):
                            self.error = (f'invalid {check[1]}', 400)
                            break
                        utyp = get_unit_type(self.cur, val)
                        if utyp is None:
                            self.error = (f'{check[1]} does not exist', 404)
                            break
                        self.__dict__[check[0]+'_type'] = utyp
                self.__dict__[check[0]] = val
    def modify(self, uid):
        self.cur.execute('UPDATE objects SET modified = ? WHERE id = ?',
                         (self.now, uid))

def json_args(*checks):
    def dec(fn):
        @functools.wraps(fn)
        def _fn():
            a = Args(checks)
            if a.error is not None:
                return a.error
            return fn(a)
        return _fn
    return dec

@app.post('/createProject')
@json_args(('project', 'project id', str))
def create_project(args):
    pth = get_path(args.project, 'data.db')
    Path(os.path.dirname(pth)).mkdir(parents=True, exist_ok=True)
    if os.path.exists(pth):
        return {'error': 'project already exists'}, 400
    con = sql.connect(pth)
    con.executescript(NEW_DB_SCRIPT)
    return {'message': 'created project '+args.project}

@app.post('/createType')
@json_args(('project', 'project id', 'project'), ('type', 'unit type', str))
def create_type(args):
    args.cur.execute('SELECT * FROM tiers WHERE unittype = ? LIMIT 1', (args.type,))
    if args.cur.fetchone() is not None:
        return {'error': 'type already exists'}, 400
    args.cur.execute('INSERT INTO tiers(tier, feature, unittype, valuetype) VALUES(?, ?, ?, ?)', ('meta', 'active', args.type, 'bool'))
    args.con.commit()
    return {'message': 'created unit type '+args.type}

def check_meta_field(feature, vtype):
    if feature == 'parent' and vtype == 'ref':
        return True
    if feature == 'index' and vtype == 'int':
        return True
    return False

@app.post('/createFeature')
@json_args(('project', 'project id', 'project'), ('unittype', 'unit type', str),
           ('tier', 'tier name', str), ('feature', 'feature name', str),
           ('valuetype', 'value type', str))
def create_feature(args):
    if args.valuetype not in ['int', 'bool', 'str', 'ref']:
        return {'error': 'invalid value type'}, 400
    if args.tier == 'meta':
        if not check_meta_field(args.feature, args.valuetype):
            return {'error': 'invalid meta field'}, 400
    args.cur.execute('SELECT * FROM tiers WHERE unittype = ? LIMIT 1', (args.unittype,))
    if args.cur.fetchone() is None:
        return {'error': 'unit type does not exist'}, 400
    args.cur.execute('INSERT INTO tiers(tier, feature, unittype, valuetype) VALUES(?, ?, ?, ?)', (args.tier, args.feature, args.unittype, args.valuetype))
    args.con.commit()
    return {'message': f'created feature {args.tier}:{args.feature} for unit type {args.unittype}'}

@app.post('/createUnit')
@json_args(('project', 'project id', 'project'), ('type', 'unit type', str))
def create_unit(args):
    args.cur.execute('SELECT * FROM tiers WHERE unittype = ? LIMIT 1', (args.type,))
    if args.cur.fetchone() is None:
        return {'error': 'unknown unit type'}, 400
    args.cur.execute('INSERT INTO objects(type, created, modified, active) VALUES(?, ?, ?, ?)',
                     (args.type, args.now, args.now, 1))
    uid = args.cur.lastrowid
    # set as confirmed if we got a username in the input
    if 'user' in args.data:
        args.cur.execute(
            'INSERT INTO bool_features(id, feature, value, date, active, user) VALUES (?, ?, ?, ?, ?, ?)',
            (uid, 'meta:active', 1, args.now, 1, args.data['user'])
        )
    else:
        args.cur.execute('INSERT INTO bool_features(id, feature, value, date, active) VALUES (?, ?, ?, ?, ?)', (uid, 'meta:active', 0, args.now, 1))
    args.con.commit()
    return {'id': uid}

@app.post('/get')
@json_args(('project', 'project id', 'project'), ('item', 'item id', int))
def get_unit(args):
    obj = get_object(args.cur, args.item)
    if obj is None:
        return {'error': 'not found'}, 404
    return obj

@app.post('/setFeature')
@json_args(('project', 'project id', 'project'), ('item', 'item id', 'unit'),
           ('features', 'feature list', list), ('user', 'username', str),
           ('confidence', 'confidence score', int))
def set_feature(args):
    feats = {
        'str': [],
        'int': [],
        'bool': [],
        'ref': [],
    }
    expected_keys = ['feature', 'tier', 'value']
    for f in args.features:
        if sorted(f.keys()) != expected_keys:
            return {'error': 'invalid feature list'}, 400
        args.cur.execute('SELECT valuetype FROM tiers WHERE tier = ? AND feature = ? AND unittype = ?', (f['tier'], f['feature'], args.item_type))
        vtyp = args.cur.fetchone()
        feat = f'{f["tier"]}:{f["feature"]}'
        if vtyp is None:
            return {'error': feat+' does not exist for type '+args.item_type}, 404
        if vtyp[0] == 'str' and isinstance(f['value'], str):
            feats['str'].append({'f': feat, 'v': f['value']})
        elif vtyp[0] in ['int', 'ref'] and isinstance(f['value'], int):
            feats[vtyp].append({'f': feat, 'v': f['value']})
        elif vtyp[0] == 'bool' and isinstance(f['value'], bool):
            feats['bool'].append({'f': feat, 'v': int(f['value'])})
        else:
            return {'error': 'invalid feature list'}, 400
    update_count = 0
    for typ in feats:
        if not feats[typ]:
            continue
        qr = 'UPDATE %s_features SET active = 0 WHERE id = ? AND feature IN (%s)' % (typ, ', '.join('?' for _ in feats[typ]))
        args.cur.execute(qr, [args.item] + [f['f'] for f in feats[typ]])
        for f in feats[typ]:
            args.cur.execute(
                '''
INSERT INTO %s_features(id, feature, value, user, confidence, date, active)
VALUES (?, ?, ?, ?, ?, ?, ?)
''' % typ,
                [
                    args.item,       # id
                    f['f'],          # feature
                    f['v'],          # value
                    args.user,       # user
                    args.confidence, # confidence
                    args.now,        # date
                    1,               # active
                ]
            )
            update_count += 1
    args.modify(args.item)
    args.con.commit()
    return {'updates': update_count, 'time': args.now}

@app.post('/setParent')
@json_args(('project', 'project id', 'project'), ('parent', 'parent id', 'unit'),
           ('child', 'child id', 'unit'))
def set_parent(args):
    args.cur.execute('UPDATE relations SET active = 0 WHERE parent = ? AND child = ? AND isprimary = 1', (args.parent, args.child))
    args.cur.execute('INSERT INTO relations(parent, parent_type, child, child_type, isprimary, active, date) VALUES (?, ?, ?, ?, 1, 1, ?)', (args.parent, args.parent_type, args.child, args.child_type, args.now))
    args.modify(args.parent)
    args.modify(args.child)
    args.con.commit()
    return {'message': 'parent set', 'time': args.now}

@app.post('/addParent')
@json_args(('project', 'project id', 'project'), ('parent', 'parent id', 'unit'),
           ('child', 'child id', 'unit'))
def add_parent(args):
    args.cur.execute('INSERT INTO relations(parent, parent_type, child, child_type, isprimary, active, date) VALUES (?, ?, ?, ?, 0, 1, ?)', (args.parent, args.parent_type, args.child, args.child_type, args.now))
    args.modify(args.parent)
    args.modify(args.child)
    args.con.commit()
    return {'message': 'parent added', 'time': args.now}

@app.post('/removeParent')
@json_args(('project', 'project id', 'project'), ('parent', 'parent id', 'unit'),
           ('child', 'child id', 'unit'))
def rem_parent(args):
    args.cur.execute('UPDATE relations SET active = 0 WHERE parent = ? AND child = ?', (args.parent, args.child))
    args.modify(args.parent)
    args.modify(args.child)
    return {'message': 'parent removed', 'time': args.now}

@app.post('/listType')
@json_args(('project', 'project id', 'project'), ('type', 'unit type', str),
           ('tier', 'tier name', str), ('feature', 'feature name', str))
def list_type(args):
    args.cur.execute('SELECT valuetype FROM tiers WHERE unittype = ? AND tier = ? AND feature = ?', (args.type, args.tier, args.feature))
    vt = args.cur.fetchone()
    if vt is None:
        return {'error': 'unit type or feature does not exist'}, 400
    args.cur.execute('SELECT id FROM objects WHERE type = ? AND active = 1', (args.type,))
    dct = {k[0]:None for k in args.cur.fetchall()}
    if not dct:
        return {'units': []}
    qs = ', '.join('?' for _ in range(len(dct)))
    args.cur.execute(f'SELECT id, value FROM {vt[0]}_features WHERE id IN ({qs}) AND feature = ? AND user IS NOT NULL AND active = 1',
                     list(dct.keys()) + [args.tier+':'+args.feature])
    for i, v in args.cur.fetchall():
        dct[i] = bool(v) if vt[0] == 'bool' else v
    ls = list(dct.items())
    ls.sort()
    return {'units': [{"id": i, "value": v} for i,v in ls]}

@app.post('/modificationTimes')
@json_args(('project', 'project id', 'project'), ('ids', 'id list', list))
def modification_times(args):
    qs = ', '.join('?' for _ in args.ids)
    args.cur.execute(f'SELECT id, modified FROM objects WHERE id IN ({qs})', args.ids)
    return dict(args.cur.fetchall())
