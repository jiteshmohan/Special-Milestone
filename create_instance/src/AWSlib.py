import boto.ec2
import random,os,time
from Crypto.PublicKey import RSA

import argparse
import time
try:
    from configparser import ConfigParser
except ImportError:
    from ConfigParser import ConfigParser

class AWSInstance(object):
    def __init__(self,config):
        self.ip = None
        self.secgrp = None
        if 'aws_region' in config.options('aws'):
            if config.get('aws','aws_region') in [x.__str__().split(':')[1] for x in boto.ec2.regions()]:
                self.region = config.get('aws','aws_region')
            else:
                self.region = random.choice([x.__str__().split(':')[1] for x in boto.ec2.regions()])
        else:
            self.region = random.choice([x.__str__().split(':')[1] for x in boto.ec2.regions()])
        print 'Region chosen:',self.region
        #Connecting to aws
        self.conn = boto.ec2.connect_to_region(self.region,aws_access_key_id=config.get('aws','aws_access_key_id'),aws_secret_access_key=config.get('aws','aws_secret_access_key'))
        if self.conn == None:
            print 'Unable to connect'
            return None
        else:
            print 'Connection created successfully'
        #Adding key to AWS
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
                key_pair = self.conn.import_key_pair(os.environ['USER'],key)
            print 'Key pushed to server.'
        except boto.exception.EC2ResponseError:
            print 'Key already exists!'
        #Creating a security group to allow ssh
        sshflag = 0
        httpflag = 0
        print 'Checking if ssh and http rules exist in security group'
        for eachgrp in self.conn.get_all_security_groups():
            if eachgrp.name == os.environ['USER']:
                self.secgrp = eachgrp
                for eachrule in eachgrp.rules:
                    if eachrule.ip_protocol == 'tcp' and int(eachrule.from_port) <= 22 and int(eachrule.to_port)>=22:
                        sshflag = 1
                    if eachrule.ip_protocol == 'tcp' and int(eachrule.from_port) <= 80 and int(eachrule.to_port)>=80:
                        httpflag = 1
                    if sshflag and httpflag:
                        break
            if sshflag and httpflag:
                break
        #Need to create a new security group
        if sshflag == 0:
            if self.secgrp is None:
                self.secgrp = self.conn.create_security_group(os.environ['USER'], os.environ['USER'])
            self.secgrp.authorize('tcp', 22, 22, '0.0.0.0/0')
            print 'Creating a rule for ssh in security group'
        if httpflag == 0:
            if self.secgrp is None:
                self.secgrp = self.conn.create_security_group(os.environ['USER'], os.environ['USER'])
            self.secgrp.authorize('tcp', 80, 80, '0.0.0.0/0')
            print 'Creating a rule for http in security group'

        #Selecting os-image to install
        imagelist = self.conn.get_all_images(owners='099720109477', filters={ 'architecture' : 'x86_64' })
        self.image = random.choice([image for image in imagelist  if 'ubuntu-14.04' in image.name])
        del imagelist
        print 'Image selected:',self.image
        self.keyname = os.environ['USER']
        self.instancetype = config.get('aws','aws_instance_type')
        print 'Instance size:',self.instancetype
        print 'Creating instance'
        self.instance = self.conn.run_instances(self.image.id, key_name=self.keyname, instance_type=self.instancetype,security_groups=[self.secgrp])
        self.id = self.instance.id
        print 'Instance creation successful'

    def getIp(self):
        if self.ip == None:
            for eachinstance in self.conn.get_all_instances():
                if eachinstance.id == self.id:
                    self.ip = eachinstance.instances[0].ip_address
                    break
        return self.ip

if __name__=="__main__":
    config = ConfigParser()
    config.read('../config.ini')
    instanceObj = AWSInstance(config)
    time.sleep(30)
    print instanceObj.getIp()
