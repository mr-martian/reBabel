#!/usr/bin/env python3

from flask import Flask, request
import sqlite3 as sql # definitely not permanent
import os.path
import datetime
import json
from pathlib import Path

app = Flask('core')

# TODO - from cmdline or config file probably
PROJECT_DIR = os.path.join(
    os.path.dirname(os.path.realpath(__file__)),
    'projects/'
)
TIME_FORMAT = '%Y-%m-%d %H:%M:%S'

def get_path(projectid, fname):
    return os.path.join(PROJECT_DIR, f'{projectid}/', fname)

NEW_DB_SCRIPT = '''
BEGIN;
-- TODO: created as timestamp and active as bool
CREATE TABLE objects(id INTEGER PRIMARY KEY,
                     type TEXT,
                     created TEXT,
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
    cur.execute('SELECT type FROM objects WHERE id = ? AND active = 1;', [objectid])
    result = cur.fetchone()
    if result is None:
        return None
    otype = result[0]
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
        'layers': layers,
        'children': children,
    }

def check_args(dct, *checks):
    for c in checks:
        if c[0] not in request.json:
            return {'error': f'{c[1]} is required'}, 400
        if len(c) > 2:
            try:
                dct[c[0]] = c[2](request.json[c[0]])
            except:
                return {'error': f'invalid {c[1]}'}, 400
        else:
            dct[c[0]] = request.json[c[0]]

@app.route('/createProject', methods=['POST'])
def create_project():
    d = {}
    r = check_args(d, ('project', 'project id'))
    if r is not None:
        return r
    pth = get_path(d['project'], 'data.db')
    Path(os.path.dirname(pth)).mkdir(parents=True, exist_ok=True)
    if os.path.exists(pth):
        return {'error': 'project already exists'}, 400
    con = sql.connect(pth)
    con.executescript(NEW_DB_SCRIPT)
    return {'message': 'created project '+d['project']}

@app.post('/createType')
def create_type():
    d = {}
    r = check_args(d, ('project', 'project id'), ('type', 'unit type'))
    if r is not None:
        return r
    pth = get_path(d['project'], 'data.db')
    con = sql.connect(pth)
    cur = con.cursor()
    cur.execute('SELECT * FROM tiers WHERE unittype = ? LIMIT 1', (d['type'],))
    if cur.fetchone() is not None:
        return {'error': 'type already exists'}, 400
    cur.execute('INSERT INTO tiers(tier, feature, unittype, valuetype) VALUES(?, ?, ?, ?)', ('meta', 'active', d['type'], 'bool'))
    con.commit()
    return {'message': 'created unit type '+d['type']}

@app.route('/createUnit', methods=['POST'])
def create_unit():
    d = {}
    r = check_args(d, ('project', 'project id'), ('type', 'unit type'))
    if r is not None:
        return r
    pth = get_path(d['project'], 'data.db')
    con = sql.connect(pth)
    cur = con.cursor()
    cur.execute('SELECT * FROM tiers WHERE unittype = ? LIMIT 1', (d['type'],))
    if cur.fetchone() is None:
        return {'error': 'unknown unit type'}, 400
    ts = datetime.datetime.now().strftime(TIME_FORMAT)
    cur.execute('INSERT INTO objects(type, created, active) VALUES(?, ?, ?)',
                (d['type'], ts, 1))
    uid = cur.lastrowid
    # TODO: assumes new units are unconfirmed, but would unconfirmed units
    # generally come from suggestions and thus this API should assume that
    # new units are confirmed?
    cur.execute('INSERT INTO bool_features(id, feature, value, date, active) VALUES (?, ?, ?, ?, ?)', (uid, 'meta:active', 0, ts, 1))
    con.commit()
    return {'id': uid}

@app.route('/get', methods=['POST'])
def get_unit():
    d = {}
    r = check_args(d, ('project', 'project id'), ('item', 'item id', int))
    if r is not None:
        return r
    pth = get_path(d['project'], 'data.db')
    if not os.path.exists(pth):
        return {'error': 'project does not exist'}, 404
    con = sql.connect(pth)
    cur = con.cursor()
    obj = get_object(cur, d['item'])
    if obj is None:
        return {'error': 'not found'}, 404
    return obj

@app.route('/setFeature', methods=['POST'])
def set_feature():
    d = {}
    r = check_args(d, ('project', 'project id'), ('item', 'item id', int),
                   ('features', 'feature list'), ('user', 'username'),
                   ('confidence', 'confidence score', float))
    if r is not None:
        return r
    expected_keys = ['feature', 'tier', 'value']
    if not isinstance(d['features'], list):
        return {'error': 'invalid feature list'}, 400
    feats = {
        'str': [],
        'int': [],
        'bool': [],
        'ref': [],
    }
    # TODO: validate that project exists
    pth = get_path(d['project'], 'data.db')
    con = sql.connect(pth)
    cur = con.cursor()
    cur.execute('SELECT type FROM objects WHERE id = ?', (d['item'],))
    typ = cur.fetchone()
    if typ is None:
        return {'error': 'item does not exist'}, 404
    for f in d['features']:
        if sorted(f.keys()) != expected_keys:
            return {'error': 'invalid feature list'}, 400
        cur.execute('SELECT valuetype FROM tiers WHERE tier = ? AND feature = ? AND unittype = ?', (f['tier'], f['feature'], typ))
        vtyp = cur.fetchone()
        feat = f'{f["tier"]}:{f["feature"]}'
        if vtyp is None:
            return {'error': feat+' does not exist for type '+typ}, 404
        if vtyp == 'str' and isinstance(f['value'], str):
            feats['str'].append({'f': feat, 'v': f['value']})
        elif vtyp in ['int', 'ref'] and isinstance(f['value'], int):
            feats[vtyp].append({'f': feat, 'v': f['value']})
        elif vtyp == 'bool' and isinstance(f['value'], bool):
            feats['bool'].append({'f': feat, 'v': int(f['value'])})
        else:
            return {'error': 'invalid feature list'}, 400
    ts = datetime.datetime.now().strftime(TIME_FORMAT)
    update_count = 0
    for typ in feats:
        if not feats[typ]:
            continue
        qr = 'UPDATE %s_features SET active = 0 WHERE id = ? AND feature IN (%s)' % (typ, ', '.join('?' for _ in feats[typ]))
        cur.execute(qr, [d['item']] + [f['f'] for f in feats[typ]])
        for f in feats[typ]:
            cur.execute(
                '''
INSERT INTO %s_features(id, feature, value, user, confidence, date, active)
VALUES (?, ?, ?, ?, ?, ?, ?)
''' % typ,
                [
                    d['item'],       # id
                    f['f'],          # feature
                    f['v'],          # value
                    d['user'],       # user
                    d['confidence'], # confidence
                    ts,              # date
                    1,               # active
                ]
            )
            update_count += 1
    con.commit()
    return {'updates': update_count}
