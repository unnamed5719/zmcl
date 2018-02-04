#coding=utf-8

__author__ = 'unnmaed5719'
__version__ = '0.2.1'

'''
zero minecraft launcher
written in Python using Built-in module
for windows only, but can launch in other system 
by doing some modification.
thanks to wiki.vg

TODO:
Downloading Multi files at the same time 
'''


import os
import sys
import json
import ctypes
import zipfile
import subprocess
from urllib import request


class ComputerBusy(Exception):
    pass


class Yggdrasil:
    '''account verification and keeping token available'''
    def __init__(self, email, password):
        self.server_url = 'https://authserver.mojang.com/'
        self.headers = {'Content-type': 'application/json'}
        self.email = email
        self._password = password
        
    def authenticate(self):
        authenticate_url = self.server_url+'authenticate'

        auth_payload = {
            "agent": {"name": "Minecraft","version": "1"},
            "username": self.email,
            "password": self._password,
        }
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


class GameFile:
    '''download game file'''
    
    def __init__(self):
        self.version_manifest_url = 'https://launchermeta.mojang.com/mc/game/version_manifest.json'
        self.objects_url = 'http://resources.download.minecraft.net/'

    def get_latest_json_version_url(self, ver=None):
        version_manifest = json.loads(request.urlopen(self.version_manifest_url).read().decode())
        if ver:
            self.latest_version = ver
        else:
            self.latest_version = version_manifest['latest']['release']
        for version in version_manifest['versions']:
            if version['id'] == self.latest_version:
                return version['url']
            
    def get_game_json(self):
        url = self.get_latest_json_version_url()
        FilesProsess.auto_mkdir('.minecraft/versions/'+self.latest_version)
        self.game_json_file_dir = '.minecraft/versions/'+self.latest_version+'/'
        FilesProsess.downloader(url, self.game_json_file_dir+self.latest_version+'.json')
        
    def get_assetindex_json(self):
        with open(self.game_json_file_dir+self.latest_version+'.json') as game_json:
            self.json_game_json = json.loads(game_json.read())
        self.asset_index_id = self.json_game_json['assetIndex']['id']
        asset_index_url = self.json_game_json['assetIndex']['url']
        size = self.json_game_json['assetIndex']['size']
        FilesProsess.auto_mkdir('.minecraft/assets/indexes/')
        FilesProsess.downloader(asset_index_url, '.minecraft/assets/indexes/'+self.asset_index_id+'.json', size)
    
    def get_objects(self):
        with open('.minecraft/assets/indexes/'+self.asset_index_id+'.json') as objects_file:
            json_objects = json.loads(objects_file.read())
        for object in json_objects['objects']:
            hash_string = json_objects['objects'][object]['hash']
            size = json_objects['objects'][object]['size']
            FilesProsess.auto_mkdir('.minecraft/assets/objects/'+hash_string[:2])
            FilesProsess.downloader(self.objects_url+hash_string[:2]+'/'+hash_string, 
                                    '.minecraft/assets/objects/'+hash_string[:2]+'/'+hash_string, size)
            
    def get_client(self):
        client_url = self.json_game_json['downloads']['client']['url']
        size = self.json_game_json['downloads']['client']['size']
        FilesProsess.downloader(client_url, self.game_json_file_dir+self.latest_version+'.jar', size)
    
    def get_libraries(self):
        class_path = ''
        self.cwd = os.getcwd().replace('\\','/')+'/'
        for library in self.json_game_json['libraries']:
            if 'extract' in library:
                if 'rules' in library:
                    if len(library['rules']) == 1: # when it is 2, we download it, just don't know how to handle this
                        print(library['name'],"isn't for current system, ignore")
                        continue
                url = library['downloads']['classifiers']['natives-windows']['url']
                size = library['downloads']['classifiers']['natives-windows']['size']
                _, file_name = os.path.split(url)
                FilesProsess.auto_mkdir(self.game_json_file_dir+'natives')
                FilesProsess.downloader(url, self.game_json_file_dir+'natives/'+file_name, size)
                FilesProsess.unzip(self.game_json_file_dir+'natives/'+file_name, self.game_json_file_dir+'natives')
                # os.remove(self.game_json_file_dir+'/natives/'+file_name) 
                # we don't need it any more, but will cost unnecessary download
            elif 'rules' in library:
                if len(library['rules']) == 1: 
                    print(library['name'],"isn't for current system, ignore")
                    continue
                else:
                    url = library['downloads']['artifact']['url']
                    size = library['downloads']['artifact']['size']
                    full_path = url.replace('https://libraries.minecraft.net','.minecraft/libraries')
                    file_path, _ = os.path.split(full_path)
                    FilesProsess.auto_mkdir(file_path)
                    FilesProsess.downloader(url, full_path, size)
                    class_path += self.cwd+full_path+';'
            else:
                url = library['downloads']['artifact']['url']
                size = library['downloads']['artifact']['size']
                full_path = url.replace('https://libraries.minecraft.net','.minecraft/libraries')
                file_path, _ = os.path.split(full_path)
                FilesProsess.auto_mkdir(file_path)
                FilesProsess.downloader(url, full_path, size)
                class_path += self.cwd+full_path+';'
        return class_path
        
    def get_arguments(self):
        arguments = self.json_game_json['minecraftArguments']
        main_class = self.json_game_json['mainClass']
        return main_class+' '+arguments.replace('$','')

class FilesProsess:
    '''process file'''
    
    def auto_mkdir(dirs):
        if not os.path.exists(dirs):
            os.makedirs(dirs)

    def downloader(url, path, size=None):# path aka path + file name
        if os.path.exists(path) and os.path.getsize(path) == (size if size else os.path.getsize(path)):
        # if we got size, check is it same? otherwise check it is non-zero-size
            print(path,'is already exists, pass')
        else:
            print('Downloading',path) 
            def process_bar(blocknum, blocksize, totalsize):
                # https://docs.python.org/3/library/urllib.request.html#urllib.request.retrieve
                percent = 100 * blocknum * blocksize / totalsize
                if percent > 100: # don't know why most time will more than 100,
                    percent = 100 # probably is file size + one percent of the file size.
                print("Total %.2f MB  %.2f%%." %(totalsize/1048576, percent), end='\r')
                # every time it call this function, refresh both variate, little bit unnecessary
            request.urlretrieve(url, path, process_bar) 
            print('Done!')                               
    
    def unzip(file, file_path):
        if os.path.exists(file): # check if downloaded but haven't unzip
            zf = zipfile.ZipFile(file)
            for zip_list in zf.filelist:
                if os.path.exists(file_path+'/'+zip_list.orig_filename):
                    print(zip_list.orig_filename, 'is already extracted, pass')
                else:
                    with zipfile.ZipFile(file) as zip_file:
                        zip_file.extractall(file_path)
        else: # how to avoid copy and paste like this?
            with zipfile.ZipFile(file) as zip_file:
                zip_file.extractall(file_path)

class ConfigFile:
    '''read/write configuration file'''
    
    def __init__(self):
        self.config_file_name = 'config.json'
    def write_config(self, **kwargs):        
        with open(self.config_file_name, 'w') as config_file:
            config_file.write(json.dumps(kwargs, indent=4))
    def read_config(self):
        with open(self.config_file_name, 'r') as config_file:
            self.config_json = json.loads(config_file.read())
        self.clientToken = self.config_json['clientToken']
        self.accessToken = self.config_json['accessToken']
        self.display_name = self.config_json['display_name']
        self.current_version = self.config_json['current_version']
        self.expires_time = self.config_json['expires_time']
        self.uuid = self.config_json['uuid']
        self.email = self.config_json['email']

class mem_class(ctypes.Structure):
    '''get windows memory'''
    # From https://stackoverflow.com/questions/2017545/
    _fields_ = [
        ("dwLength", ctypes.c_ulong),             # sizeof(mem_class)
        ("dwMemoryLoad", ctypes.c_ulong),         # percent of memory in use
        ("ullTotalPhys", ctypes.c_ulonglong),     # bytes of physical memory
        ("ullAvailPhys", ctypes.c_ulonglong),     # free physical memory bytes
        ("ullTotalPageFile", ctypes.c_ulonglong), # bytes of paging file
        ("ullAvailPageFile", ctypes.c_ulonglong), # free bytes of paging file
        ("ullTotalVirtual", ctypes.c_ulonglong),  # user bytes of address space
        ("ullAvailVirtual", ctypes.c_ulonglong),  # free user bytes
        ("sullAvailExtendedVirtual", ctypes.c_ulonglong), # always 0
    ]

    def __init__(self):
        # have to initialize this to the size of mem_class
        self.dwLength = ctypes.sizeof(self)
        super(mem_class, self).__init__()

        
def get_memory():
    stat = mem_class()
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
    mem = stat.ullAvailPhys/1073741824 # GiB here
    if mem < 1:
        raise ComputerBusy('Computer is busy now.')       
    return '-Xmx'+str(int(mem))+'G' # Yes, not round()

def record_cmd(arg):
    proc = subprocess.Popen(arg, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    while 1:
        out = proc.stdout.readline()
        if out == b'':
            break
        yield out.rstrip()

encoding = sys.stdout.encoding
def execute_cmd(arg):
    for i in record_cmd(arg):
        print(i.decode(encoding))


if __name__ == '__main__':
    import time
    import getpass
    if not os.path.exists('.minecraft'):
        email = input('Email:')
        yggdrasil = Yggdrasil(email, getpass.getpass())  
        current_version = None
        yggdrasil.authenticate() # sometimes we got 403, don't know why.
        
    else:    
        config_file = ConfigFile()
        config_file.read_config()
        accessToken = config_file.accessToken
        clientToken = config_file.clientToken
        email = config_file.email
        uuid = config_file.uuid
        display_name = config_file.display_name
        current_version = config_file.current_version
        expires_time = config_file.expires_time

        if int(expires_time) < time.time():
            print('accessToken is expired, please login again.')
            yggdrasil = Yggdrasil(email, getpass.getpass())  
            yggdrasil.authenticate()
           
        else:
            yggdrasil = Yggdrasil(email, '')
            yggdrasil.refresh(accessToken, clientToken)
        
    game_file = GameFile()
    game_file.get_latest_json_version_url(current_version) # to upgrade, just remove current_version !!NOT TESTED YET!!
    game_file.get_game_json()
    game_file.get_assetindex_json()
    game_file.get_objects()
    game_file.get_client()
    class_path = game_file.get_libraries()
    arguments = game_file.get_arguments()
    
    natives_dir = game_file.cwd+game_file.game_json_file_dir+'natives'
    
    config_file = ConfigFile()
    config_file.write_config(
        clientToken = yggdrasil.clientToken,
        accessToken = yggdrasil.accessToken,
        display_name = yggdrasil.display_name,
        uuid = yggdrasil.uuid,
        email = yggdrasil.email,
        current_version = game_file.latest_version,
        expires_time = str(int(time.time()+2592000)) # a month
    )
    
    mc_arg = arguments.format(
        auth_player_name = yggdrasil.display_name,
        version_name =  game_file.latest_version,
        game_directory = game_file.cwd+'/.minecraft', # or +/version/{version} for multi-version
        assets_root = game_file.cwd+'/.minecraft/assets',
        assets_index_name = game_file.asset_index_id,
        auth_uuid = yggdrasil.uuid,
        auth_access_token = yggdrasil.accessToken,
        user_type = 'mojang', # or legacy 
        version_type = 'release'
    ) 
    
    final_args = 'javaw.exe -XX:+UseG1GC -XX:-UseAdaptiveSizePolicy -XX:-OmitStackTraceInFastThrow '+ \
        get_memory() + ' -Djava.library.path=' + natives_dir +\
        ' -Dfml.ignoreInvalidMinecraftCertificates=true -Dfml.ignorePatchDiscrepancies=true -cp ' + class_path + \
        game_file.game_json_file_dir+game_file.latest_version+'.jar ' + mc_arg
    
    execute_cmd(final_args)

