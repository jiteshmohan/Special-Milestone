import digitalocean,redis
import random,os,time
from Crypto.PublicKey import RSA


class DOInstance(object):
    def __init__(self,config):
        self.ip = None
        self.secgrp = None
        #Creating a connectin manager
        self.connmgr = digitalocean.Manager(token=config.get('digitalocean','do_token'))
        print 'Setting up a manager for the account.'
        if 'do_region' in config.options('digitalocean'):
            if config.get('digitalocean','do_region') in [x.slug for x in self.connmgr.get_all_regions()]:
                self.region = config.get('digitalocean','do_region')
            else:
                self.region = random.choice([x.slug for x in self.connmgr.get_all_regions()])
        else:
            self.region = random.choice([x.slug for x in self.connmgr.get_all_regions()])
        print 'Region chosen:',self.region
        #Adding an SSH Key if required
        print 'Checking if private key needs to be pushed.'
        try:
            key=RSA.generate(2048)
            if os.path.exists(os.environ['PWD']+'/key/') is not True:
                os.mkdir(os.environ['PWD']+'/key/')
            keyfilename = os.environ['PWD']+'/key/private.key'
            if os.path.exists(keyfilename) is False:
                with open(keyfilename, 'w') as keyfile:
                    os.chmod(keyfilename, 0600)
                    keyfile.write(key.exportKey('PEM'))
            pubkey = key.publickey()
            pubkeyfilename = os.environ['PWD']+'/key/private.key.pub'
            if os.path.exists(pubkeyfilename) is False:
                with open(pubkeyfilename, 'w') as keyfile:
                    os.chmod(pubkeyfilename, 0600)
                    keyfile.write(pubkey.exportKey('OpenSSH'))
            with open(pubkeyfilename) as keyfile:
                key = keyfile.read()
            #with open(os.environ['HOME']+'/.ssh/id_rsa.pub') as keyfile:
            #    key = keyfile.read()
            newkeyInstance = digitalocean.SSHKey()
            newkeyInstance.token = config.get('digitalocean','do_token')
            newkeyInstance.public_key = key
            newkeyInstance.create()
            self.keyid = newkeyInstance.id
            print 'Key pushed to server.'
        except digitalocean.baseapi.DataReadError:
            print 'Key already exists!'
            for eachkey in self.connmgr.get_all_sshkeys():
                if key.strip() in eachkey.public_key:
                    self.keyid = eachkey.id
                    break

        #Selecting os-image to install
        if config.has_option('digitalocean','do_image_id'):
            self.image = config.get('digitalocean','do_image_id')
        else:
            self.image = None
        imagelist = self.connmgr.get_all_images()
        if self.image not in [x.slug for x in imagelist if x.slug is not None]:
            self.image = random.choice([x.slug for x in imagelist if x.slug is not None and 'ubuntu' in x.slug and 'x64' in x.slug])
        del imagelist
        print 'Image chosen:',self.image
        #Choosing size of the droplet
        r = redis.StrictRedis(host='localhost', port=6379, db=0)
        sizelist=r.get('sizelist').split(',')
        currsize=r.get('currsize')
        limitlist=r.get('limitlist').split(',')
        index=0
        currlimit=0
        for eachsize in sizelist:
            if eachsize==currsize:
                break
            index+=1
        if index+1<len(sizelist):
            self.instancetype = sizelist[index+1]
            currlimit = limitlist[index+1]
        else:
            self.instancetype = sizelist[-1]
            currlimit = limitlist[-1]
        r.set('currsize',self.instancetype)
        print 'Droplet size:',self.instancetype
        self.droplet = digitalocean.Droplet(token=newkeyInstance.token,
            name=os.environ['USER']+str(len(self.connmgr.get_all_droplets())+1),
            region=self.region,
            image=self.image,
            size_slug=self.instancetype,
            backups=False,
            ssh_keys=[self.keyid])
        print 'Creating droplet'
        self.droplet.create()
        print 'Droplet creation successful'
        for index in range(60):
            if self.connmgr.get_droplet(self.droplet.id).status.strip() == 'active':
                break
            if index%5 == 0:
                print 'Current droplet Status:',self.connmgr.get_droplet(self.droplet.id).status.strip()
            time.sleep(5)

        if self.connmgr.get_droplet(self.droplet.id).status.strip() != 'active':
            return None

    def getIp(self):
        if self.ip == None:
            self.ip = self.connmgr.get_droplet(self.droplet.id).ip_address
        return self.ip


if __name__=="__main__":
    config = ConfigParser()
    config.read('../config.ini')
    instanceObj = DOInstance(config)
    print instanceObj.getIp()
