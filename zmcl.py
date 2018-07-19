#coding=utf-8

__author__ = 'unnmaed5719'
__version__ = '0.2.5'

'''
https://github.com/unnamed5719/zmcl
LICENSE:MIT
zero minecraft launcher
written in Python using Built-in module.
for modern vanilla Minecraft.
thanks to wiki.vg
'''


import os
import sys
import json
import zipfile
import subprocess
from queue import Queue
from urllib import request
from threading import Thread


class Yggdrasil:
    '''account verification and keeping token available'''

    def __init__(self, email, password, clientToken):
        self.server_url = 'https://authserver.mojang.com/'
        self.headers = {'Content-type': 'application/json'}
        self.clientToken = clientToken
        self.email = email
        self._password = password

    def authenticate(self):
        authenticate_url = self.server_url+'authenticate'

        auth_payload = {
            "agent": {"name": "Minecraft", "version": "1"},
            "username": self.email,
            "password": self._password
        }
        if self.clientToken:
            auth_payload['clientToken'] = self.clientToken
        
        auth_requ = request.Request(url=authenticate_url,
                                    headers=self.headers,
                                    data=json.dumps(auth_payload).encode())

        auth_resp = json.loads(request.urlopen(auth_requ).read().decode())

        self.accessToken = auth_resp['accessToken']
        self.clientToken = auth_resp['clientToken']
        self.uuid = auth_resp['selectedProfile']['id']
        self.display_name = auth_resp['selectedProfile']['name']
        # Looks like 'selectedProfile' is a list version of 'availableProfiles', not sure.
        return True

    def refresh(self, accessToken, clientToken):
        refresh_url = self.server_url+'refresh'

        refresh_payload = {
            "accessToken": accessToken,
            "clientToken": clientToken
        }
        refresh_requ = request.Request(url=refresh_url,
                                       headers=self.headers,
                                       data=json.dumps(refresh_payload).encode())

        refresh_resp = json.loads(request.urlopen(refresh_requ).read().decode())

        self.accessToken = refresh_resp['accessToken']
        self.clientToken = refresh_resp['clientToken']
        self.uuid = refresh_resp['selectedProfile']['id']
        self.display_name = refresh_resp['selectedProfile']['name']

        return True

    def validate(self, accessToken, clientToken):
        validate_url = self.server_url+'validate'

        validate_payload = {
            "accessToken": accessToken,
            "clientToken": clientToken
        }
        
        validate_requ = request.Request(url=validate_url,
                                        headers=self.headers,
                                        data=json.dumps(validate_payload).encode())

        request.urlopen(validate_requ).read().decode()

        return True


class GameFile:
    '''download game file'''

    def __init__(self):
        self.version_manifest_url = 'https://launchermeta.mojang.com/mc/game/version_manifest.json'
        self.objects_url = 'http://resources.download.minecraft.net/'
        FilesProsess.auto_mkdir('.minecraft')

    def get_latest_json_version_url(self, ver, ver_type):
        if not os.path.exists('.minecraft/version_manifest.json'):
            FilesProsess.local_dler(self.version_manifest_url,'.minecraft/version_manifest.json')
        with open('.minecraft/version_manifest.json') as file:
            version_manifest = json.loads(file.read())
        if ver:
            self.latest_version = ver
        else:
            self.latest_version = version_manifest['latest'][ver_type]
        for version in version_manifest['versions']:
            if version['id'] == self.latest_version:
                return version['url']

    def get_game_json(self, ver, ver_type):
        url = self.get_latest_json_version_url(ver, ver_type)
        FilesProsess.auto_mkdir('.minecraft/versions/'+self.latest_version)
        self.game_json_file_dir = '.minecraft/versions/'+self.latest_version+'/'
        FilesProsess.local_dler(url, self.game_json_file_dir+self.latest_version+'.json')

    def get_assetindex_json(self):
        with open(self.game_json_file_dir+self.latest_version+'.json') as game_json_file:
            self.json_game_json = json.loads(game_json_file.read())
        self.asset_index_id = self.json_game_json['assetIndex']['id']
        asset_index_url = self.json_game_json['assetIndex']['url']
        size = self.json_game_json['assetIndex']['size']
        FilesProsess.auto_mkdir('.minecraft/assets/indexes/')
        FilesProsess.downloader(asset_index_url, '.minecraft/assets/indexes/'+self.asset_index_id+'.json', size)

    def get_objects(self):
        file_url_list = []
        with open('.minecraft/assets/indexes/'+self.asset_index_id+'.json') as objects_file:
            json_objects = json.loads(objects_file.read())
        for object in json_objects['objects']:
            hash_string = json_objects['objects'][object]['hash']
            size = json_objects['objects'][object]['size']
            FilesProsess.auto_mkdir('.minecraft/assets/objects/'+hash_string[:2])
            file_url_list.append([[self.objects_url+hash_string[:2]+'/'+hash_string], [size]])

        return file_url_list

    def dl_object(self):
        file_url_list = self.get_objects()

        # Create a queue to communicate with the worker threads
        queue = Queue()

        # Create 16 worker threads
        for x in range(16):
            worker = DownloadWorker(queue)
            # Setting daemon to True will let the main thread exit even though the workers are blocking
            worker.daemon = True
            worker.start()
        # Put the tasks into the queue as a tuple
        for file_url in file_url_list:
            queue.put(file_url)

        # Causes the main thread to wait for the queue to finish processing all the tasks
        queue.join()

    def get_client(self):
        client_url = self.json_game_json['downloads']['client']['url']
        size = self.json_game_json['downloads']['client']['size']
        FilesProsess.downloader(client_url, self.game_json_file_dir+self.latest_version+'.jar', size)

    def get_libraries(self):
        class_path = ''
        self.cwd = os.getcwd().replace('\\', '/')+'/'
        system, patch = ThisSystem.current_system()
        dlos = 'natives-'+system
        for library in self.json_game_json['libraries']:
            if 'natives' in library:
                if 'rules' in library:
                    if len(library['rules']) == patch:
                        # when it is 2, we download it, just don't know how to handle this
                        print(library['name'], "isn't for current system, ignore")
                        continue
                url = library['downloads']['classifiers'][dlos]['url']
                size = library['downloads']['classifiers'][dlos]['size']
                file_name = os.path.split(url)[1]
                FilesProsess.auto_mkdir(self.game_json_file_dir+'natives')
                FilesProsess.downloader(url, self.game_json_file_dir+'natives/'+file_name, size)
                FilesProsess.unzip(self.game_json_file_dir+'natives/'+file_name, self.game_json_file_dir+'natives')
            elif 'rules' in library:
                if len(library['rules']) == patch:
                    print(library['name'], "isn't for current system, ignore")
                    continue
                url = library['downloads']['artifact']['url']
                size = library['downloads']['artifact']['size']
                full_path = url.replace('https://libraries.minecraft.net', '.minecraft/libraries')
                file_path = os.path.split(full_path)[0]
                FilesProsess.auto_mkdir(file_path)
                FilesProsess.downloader(url, full_path, size)
                class_path += self.cwd+full_path+';'
            else:
                url = library['downloads']['artifact']['url']
                size = library['downloads']['artifact']['size']
                full_path = url.replace('https://libraries.minecraft.net', '.minecraft/libraries')
                file_path = os.path.split(full_path)[0]
                FilesProsess.auto_mkdir(file_path)
                FilesProsess.downloader(url, full_path, size)
                class_path += self.cwd+full_path+';'
        return class_path

    def get_arguments(self):
        if 'minecraftArguments' in self.json_game_json:
            arguments = self.json_game_json['minecraftArguments']
        else: # 1.13 new arguments is list
            a=[]
            for i in self.json_game_json['arguments']['game']:
                if isinstance(i, str):
                    a.append(i)
            arguments = ' '.join(a)
        
        main_class = self.json_game_json['mainClass']
        return main_class+' '+arguments.replace('$', '')


class FilesProsess:
    '''process file'''
    def auto_mkdir(dirs):
        if not os.path.exists(dirs):
            os.makedirs(dirs)

    def local_dler(url, path):
        with open(path, 'wb') as file:
            file.write(request.urlopen(url).read())
        
    def downloader(url, path, size): # path aka path + file name
        if os.path.exists(path) and os.path.getsize(path) == size:
        # if we got size, check is it same
            print(path, 'is already exists, pass', end='\r')
        else:
            print('Downloading', path) 
            def process_bar(blocknum, blocksize, totalsize):
                # https://docs.python.org/3/library/urllib.request.html#urllib.request.retrieve
                percent = 100 * blocknum * blocksize / totalsize
                print('%.2f%% %.2f MB' %(percent, totalsize/1048576), end='\r')
            request.urlretrieve(url, path, process_bar)
            print('Done!  ')
                  #100.00%

    def unzip(file, file_path):
        if os.path.exists(file): # check if downloaded but haven't unzip
            zf = zipfile.ZipFile(file)
            for zip_list in zf.filelist:
                if os.path.exists(file_path+'/'+zip_list.orig_filename):
                    print(zip_list.orig_filename, 'is already extracted, pass', end='\r')
                else:
                    with zipfile.ZipFile(file) as zip_file:
                        zip_file.extractall(file_path)
        else: # how to avoid copy and paste like this?
            with zipfile.ZipFile(file) as zip_file:
                zip_file.extractall(file_path)


class DownloadWorker(Thread):
    '''parallel downloader'''
    # From https://www.jianshu.com/p/d87c951d8416

    def __init__(self, queue):
        Thread.__init__(self)
        self.queue = queue

    def run(self):
        while True:
            # Get the work from the queue and expand the tuple
            link, size = self.queue.get()
            if link is None:
                self.queue.task_done()
                break
            self.downloader(link, size)
            self.queue.task_done()

    def downloader(self, url, size):
        url = url[0]; size = size[0]
        objects_url = 'http://resources.download.minecraft.net'
        path = url.replace(objects_url, '.minecraft/assets/objects')
        if os.path.exists(path) and os.path.getsize(path) == size:
            print(path, 'is already exists, pass', end='\r')
        else:
            name = os.path.split(path)[1]
            def process_bar(blocknum, blocksize, totalsize):
                percent = 100 * blocknum * blocksize / totalsize
                if percent > 100: # don't know why most time will more than 100,
                    percent = 100 # probably is file size + one percent of the file size.
                print(name, '%.2f%% %.2f MB' %(percent, totalsize/1048576), end='\r')
            request.urlretrieve(url, path, process_bar)
            print('Done!')


class ConfigFile:
    '''read/write configuration file'''

    def __init__(self):
        self.config_file_name = 'config.json'
    def write_config(self, **kwargs):
        with open(self.config_file_name, 'w') as config_file:
            config_file.write(json.dumps(kwargs, indent=4))
    def read_config(self):
        with open(self.config_file_name, 'r') as config_file:
            config_json = json.loads(config_file.read())
        self.clientToken = config_json['clientToken']
        self.accessToken = config_json['accessToken']
        self.display_name = config_json['display_name']
        self.current_version = config_json['current_version']
        self.expires_time = config_json['expires_time']
        self.uuid = config_json['uuid']
        self.email = config_json['email']


class ThisSystem:
    '''about system'''
    def current_system():
        name = sys.platform
        if name == 'win32':
            return 'windows', 1
        elif name == 'darwin':
            return 'osx', 2
        else:
            return 'linux', 1
    
    def win_memory():
        return int(os.popen('wmic os get FreePhysicalMemory').read().split()[1])/1048576

    def unix_like_memory():
        with open('/proc/meminfo') as m:
            lines = m.readlines()   
        for line in lines:  
            if line.split(':')[0] == 'MemFree':
                var = line.split(':')[1].split()[0]  
                mem = int(var)/1048576 # GiB here
                return mem


def get_memory():
    if ThisSystem.current_system()[0] == 'windows':
        mem = ThisSystem.win_memory()
    else:
        mem = ThisSystem.unix_like_memory()
    if mem < 1: raise MemoryError('Computer is busy now.')       
    return '-Xmx'+str(int(mem))+'G'

def record_cmd(arg):
    proc = subprocess.Popen(arg, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    while 1:
        out = proc.stdout.readline()
        if out == b'':
            break
        yield out.rstrip()

def execute_cmd(arg):
    encoding = sys.stdout.encoding
    for i in record_cmd(arg):
        print(i.decode(encoding))


if __name__ == '__main__':
    import time
    import getpass
    import argparse

    config_file = ConfigFile()
    game_file = GameFile()

    parser = argparse.ArgumentParser(description='zero minecraft launcher v{}, by {}'.format(
                                     __version__, __author__))
    
    parser.add_argument('-u', '--upgrade-game', choices=['release','snapshot'],
                        help='upgrade to latest release/snapshot')
    parser.add_argument('-r', '--re-login', action='store_true', help='relogin account')
    parser.add_argument('-d', '--daemonize', action='store_true', help='daemonize')
    parser.add_argument('-s', '--screen-size', help='custom screen size, [WIDTH]x[HEIGHT]')
    parser.add_argument('-j', '--join-server', help='join a server when launched, [IP](:[PORT])')

    args = parser.parse_args()
    

    
    if not os.path.exists(config_file.config_file_name):
        email = input('Email:')
        yggdrasil = Yggdrasil(email, getpass.getpass(), None)
        yggdrasil.authenticate()
        
        current_version = None
        custom_arguments = ''
        version_type = 'release'

    else:
        config_file.read_config()
        email = config_file.email
        expires_time = config_file.expires_time
        
        custom_arguments = ''
        if args.screen_size:
            width, height = args.screen_size.split('x')
            custom_arguments += ' --width {} --height {}'.format(width, height)
        
        if args.join_server:
            s = args.join_server.split(':')
            if len(s) == 1:
                ip = s[0]; port = '25565'
            else:
                ip, port = s
            custom_arguments += ' --server {} --port {}'.format(ip, port)
          
        if args.upgrade_game:
            version_type = args.upgrade_game
            current_version = None
            os.remove('.minecraft/version_manifest.json')
        else:
            version_type = 'release'
            current_version = config_file.current_version
            
        if args.re_login:
            yggdrasil = Yggdrasil(email, getpass.getpass(), config_file.clientToken)
            yggdrasil.authenticate()
            
        else:
            yggdrasil = Yggdrasil(email, '', config_file.clientToken)
        
            if expires_time < time.time():
                yggdrasil.refresh(config_file.accessToken, config_file.clientToken)
            else:
                try:
                    yggdrasil.validate(config_file.accessToken,config_file.clientToken)
                except:
                    print('invalidated token, try refresh')
                    try:
                        yggdrasil.refresh(config_file.accessToken, config_file.clientToken)
                    except:
                        print("Someting is not quite right, try '--re-login'")
                        sys.exit(1)
                else:
                    yggdrasil = config_file
        
    game_file.get_game_json(current_version, version_type)
    
    config_file.write_config(
        clientToken = yggdrasil.clientToken,
        accessToken = yggdrasil.accessToken,
        display_name = yggdrasil.display_name,
        uuid = yggdrasil.uuid,
        email = yggdrasil.email,
        current_version = game_file.latest_version,
        expires_time = int(time.time()+2592000) # a month
    )
    
    game_file.get_assetindex_json()
    game_file.dl_object()
    game_file.get_client()
    class_path = game_file.get_libraries()
    arguments = game_file.get_arguments()

    natives_dir = game_file.cwd+game_file.game_json_file_dir+'natives'

    
    mc_arg = arguments.format(
        auth_player_name = yggdrasil.display_name,
        version_name =  game_file.latest_version,
        game_directory = game_file.cwd+'/.minecraft', 
        assets_root = game_file.cwd+'/.minecraft/assets',
        assets_index_name = game_file.asset_index_id,
        auth_uuid = yggdrasil.uuid,
        auth_access_token = yggdrasil.accessToken,
        user_type = 'mojang',
        version_type = game_file.json_game_json['type']  
    ) + custom_arguments

    final_args = 'javaw -XX:+UseG1GC -XX:-UseAdaptiveSizePolicy -XX:-OmitStackTraceInFastThrow ' + \
        get_memory() + ' -Djava.library.path=' + natives_dir + ' -cp ' + class_path + \
        game_file.game_json_file_dir + game_file.latest_version+'.jar ' + mc_arg
    
    if args.daemonize:
        def execute_cmd(arg):
            subprocess.Popen(arg, shell=True)
    
    print('='*20+'Launching begin'+'='*20)
    execute_cmd(final_args)
