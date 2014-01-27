import mechanize
import cookielib
import os
import re
import json
import pprint
import urllib
import collections

import bs4

# http://stackoverflow.com/questions/1254454/fastest-way-to-convert-a-dicts-keys-values-from-unicode-to-str
def convert(data):
    if isinstance(data, basestring):
        return str(data)
    elif isinstance(data, collections.Mapping):
        return dict(map(convert, data.iteritems()))
    elif isinstance(data, collections.Iterable):
        return type(data)(map(convert, data))
    else:
        return data

class BF4Session(object):
    def __init__(self):
        self.br = mechanize.Browser()
        self.cj = cookielib.LWPCookieJar()
        self.br.set_cookiejar(self.cj)

        if os.path.exists('mycookie.txt'):
            self.cj.load('mycookie.txt', ignore_expires=True, ignore_discard=True)

        self.ensure_session()

    def load_assets(self):
        self.get_personas()
        print 'getting lang data'
        self.data_version = None

        response = self.br.open('http://battlelog.battlefield.com/bf4/')
        data = response.read()
        soup = bs4.BeautifulSoup(data)
        
        self.assets = {}
        comp = re.compile("t\['(.*)'\]=\"(.*)\";")
        version_comp = re.compile("//eaassets-a.akamaihd.net/bl-cdn/cdnprefix/([[a-zA-Z0-9]+)/public/")

        for i in soup.find_all('script'):
            if i.attrs.get('src', False) and i.attrs['src'].endswith('en_US.js'):
                r = self.br.open('http:' + i.attrs['src'])
                d = r.read()

                for j in d.split('\n'):
                    match = comp.search(j)
                    if match:
                        key, value = match.groups()
                        self.assets[key] = value

                ## extract version.
                match = version_comp.search(i.attrs['src'])
                if match:
                    self.data_version = match.groups()[0]
                    print 'version', self.data_version

        response = self.br.open('http://eaassets-a.akamaihd.net/bl-cdn/cdnprefix/%s/public/gamedatawarsaw/warsaw.loadout.js' % self.data_version)
        data = response.read().strip()
        start_data = "game_data = "
        start = data.find(start_data) + len(start_data)
        gamedata = data[start:]
        self.gamedata = json.loads(gamedata)

        f = open('game_data_%s.json' % self.data_version, 'w')
        f.write(pprint.pformat(self.gamedata))
        f.close()

        f = open('assets_%s.json' % self.data_version, 'w')
        f.write(pprint.pformat(self.assets))
        f.close()

        ### checksum ###
        response = self.br.open('http://battlelog.battlefield.com/bf4/loadout/%s/%s/%s/#overview' % (
                self.user['username'], self.user['id'], self.user['platform']))
        data = response.read()
        comp = re.compile('"postChecksum":"([a-z0-9]+)"')
        (self.post_checksum, ) = comp.search(data).groups()

    def save(self):
        self.cj.save('mycookie.txt', ignore_discard=True)

    def login(self):
        print 'loggin in'
        self.br.open('http://battlelog.battlefield.com/bf4/gate/?reason=pass&returnUrl=|bf4|')
        form = list(self.br.forms())[0]
        
        if os.path.exists("auth.json"):
            authdata = json.loads(open('auth.json').read())
        else:
            authdata = {}
            authdata['email'] = raw_input("Origin Email:")
            authdata['password'] = raw_input("Origin Password:")

        form.set_value(authdata.get('email'), name='email')
        form.set_value(authdata.get('password'), name='password')
        
        self.br.form = form
        self.br.submit()

    def is_logged_in(self):
        response = self.br.open('http://battlelog.battlefield.com/bf4/')
        data = response.read()
        if '<section class="base-header-login-dropdown">' in data:
            return False
        else:
            return True

    def ensure_session(self):
        if self.is_logged_in():
            return True
        else:
            self.login()
            return True

    def set_current_user(self, id):
        self.user = {}
        self.user['id'] = id
        self.user['platform'] = self.users[id][1]
        self.user['username'] = self.users[id][2]
        self.user['game'] = self.users[id][3]
        self.user['is_premium'] = self.users[id][4]

    ##################################

    def player_stats(self):
        response = self.br.open('http://battlelog.battlefield.com/bf4/indexstats/%s/%s/?stats=1' % (self.user['id'], self.user['platform']))
        data = response.read()
        message = json.loads(data)
        if message['message'] == 'OK':
            return message['data']
        else:
            raise Exception('bad request')

    def weapon_stats(self):
        response = self.br.open('http://battlelog.battlefield.com/bf4/warsawWeaponsPopulateStats/%s/%s/stats/' % (self.user['id'], self.user['platform']))
        data = response.read()
        message = json.loads(data)
        if message['message'] == 'OK':
            return message['data']
        else:
            raise Exception('bad request')

    def get_full_loadout(self):
        response = self.br.open('http://battlelog.battlefield.com/bf4/loadout/get/%s/%s/%s/' % (self.user['username'], self.user['id'], self.user['platform']))
        data = response.read()
        message = json.loads(data)
        if message['message'] == 'OK':
            return message['data']
        else:
            raise Exception('bad request')
        
    def info(self):
        response = self.br.open('http://battlelog.battlefield.com/bf4/warsawoverviewpopulate/%s/%s/' % (self.user['id'], self.user['platform']))
        data = response.read()
        message = json.loads(data)
        if message['message'] == 'OK':
            return message['data']
        else:
            raise Exception('bad request')

    def get_personas(self):
        response = self.br.open('http://battlelog.battlefield.com/bf4/profile/edit/edit-soldiers/')
        soup = bs4.BeautifulSoup(response.read())
        users = {}
        comp = re.compile('/bf4/emblem/edit/(active|personal/\d+)/(\d+)/(\d+)/')

        current_user = None

        for i in soup.find_all('a', {'class':'ui-emblem'}):
            href = i.attrs['href']
            stuff, id, platform = comp.search(href).groups()
            if stuff == 'active':
                users[id] = [0, platform]
            else:
                users[id] = [1, platform]
                current_user = id

        comp2 = re.compile("/bf4/soldier/(.*)/dogtags/(\d+)/")

        for i in soup.find_all('a', {'class':'soldier-dogtags'}):
            href = i.attrs['href']
            name, id = comp2.search(href).groups()
            users[id].append(name)

        for i in soup.find_all('tr', {'class':'soldier-row'}):
            id = i.attrs['id'].split('-')[1]
            users[id].append(i.attrs['data-soldiergame'])
            users[id].append('premium' in i.attrs['class'])
        
        self.users = users
        self.set_current_user(current_user)

    def set_active_kit(self, id):
        loadout = self.get_full_loadout()
        cl = loadout.get('currentLoadout')
        cl['selectedKit'] = unicode(id)
        self.set_full_loadout(cl)

    def set_full_loadout(self, loadout):
        p = {
            'loadout': json.dumps(loadout),
            'post-check-sum':self.post_checksum,
            'platformInt': self.user['platform'],
            'game':self.user['game'],
            'personaId':self.user['id']
            }
        data = urllib.urlencode(convert(p))
        response = self.br.open('http://battlelog.battlefield.com/bf4/loadout/save/', data=data)

    def lookup(self, type, id):
        if type == 'weapon':
            return self.gamedata.get('compact', {}).get('weapons', {}).get(id, None)
        elif type == 'asset':
            return self.assets.get(id, None)

    def search(self, id):
        test = self.gamedata.get('compact', {}).get('weapons', {}).get(id, None)
        if test:
            return test

        test = self.gamedata.get('compact', {}).get('kititems', {}).get(id, None)
        if test:
            return test

        test = self.gamedata.get('compact', {}).get('appearances', {}).get(id, None)
        if test:
            return test

        return None

    def get_loadout(self, index):
        l = self.get_full_loadout()
        cl = l.get('currentLoadout')
        return cl.get('kits')[index]

    def set_loadout(self, index, data):
        l = self.get_full_loadout()
        cl = l.get('currentLoadout')
        cl.get('kits')
        cl['kits'][index] = data
        self.set_full_loadout(cl)

    def decode_loadout(self, data):
        gd = map(lambda i: self.search(i).get('name'), data)
        result = map(lambda i: self.lookup('asset', i), gd)
        return result

    def get_weapon(self, id):
        loadout = self.get_full_loadout()
        cl = loadout.get('currentLoadout')
        weapon = cl.get('weapons')
        return weapon.get(id, None)

    def set_weapon(self, id, value):
        loadout = self.get_full_loadout()
        cl = loadout.get('currentLoadout')
        cl['weapons'][id] = value
        self.set_full_loadout(cl)

if __name__ == '__main__':
    x = BF4Session()
    x.load_assets()
    x.info()

    weapon1 = lambda: x.set_weapon('3313614225', [u'1761127606', u'1176728211', u'1352321170', u'3525467546', u'78238001', u'0'])
    weapon2 = lambda: x.set_weapon('3313614225', [u'815347481', u'417382943', u'385075509', u'414305462', u'231697352', u'0'])

    setup1 = lambda: x.set_loadout(0, [u'2942558833', u'944904529', u'2887915611', u'289218432', u'3133964300', u'3214146841', u'1549533860', u'1931300281'])
    setup2 = lambda: x.set_loadout(0, [u'3313614225', u'944904529', u'2887915611', u'289218432', u'3133964300', u'3214146841', u'1549533860', u'1931300281'])
