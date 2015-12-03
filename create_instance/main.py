from src import AWSInstance
from src import DOInstance

import argparse,redis
import time,os,random,subprocess
try:
    from configparser import ConfigParser
except ImportError:
    from ConfigParser import ConfigParser

if __name__=="__main__":
    parser = argparse.ArgumentParser(description="Creates a virtual machine on a specified provider and then installs nginx on it using ansible.")
    parser.add_argument('--provider',dest='provider',required=True,type=str,nargs='?',choices=['aws','digitalocean','random'],help='Choose among aws and digitalocean as the cloud service provider')
    parser.add_argument('--config',dest='configfile',default='config.ini',type=str,nargs='?',help='Specify the location of the config file')
    parser.add_argument('--nodes',dest='numnodes',default=2,type=int,nargs='?',help='Specify the number of nodes that you need to create')
    args = parser.parse_args()
    configparser = ConfigParser()
    configparser.read(args.configfile)
    r = redis.StrictRedis(host='localhost', port=6379, db=0)
    prev_redis_ip=r.get('redis_ip')
    currlimit=int(r.get('currlimit'))
    currredisserver = redis.StrictRedis(host=prev_redis_ip, port=6379, db=0)
    while True:
        usedmemory = currredisserver.info()['used_memory']
        print 'Current memory usage:',usedmemory,'Threshold:',currlimit
        if usedmemory>currlimit:
            break
        time.sleep(10)

    inventorystr = '[servers]\n'
    if os.path.exists(os.environ['PWD']+'/key/private.key')==False:
        process=subprocess.Popen('ssh-keygen -t rsa -N "" -f key/private.key',stdout=subprocess.PIPE,stderr=subprocess.PIPE,shell=True)
        op = process.communicate()
    #    os.remove(os.environ['PWD']+'/key/private.key')
    #if os.path.exists(os.environ['PWD']+'/key/public.key'):
    #    os.remove(os.environ['PWD']+'/key/public.key')
    for index in range(args.numnodes):
        if args.provider=='random':
            providerinfo=['aws','digitalocean'][random.choice(range(10000))%2]
        else:
            providerinfo=args.provider
        if providerinfo=='digitalocean':
            print 'Creating a Droplet'
            instanceObj=DOInstance(configparser)
            username = 'root'
        elif providerinfo=='aws':
            print 'Creating an AWS instance'
            instanceObj=AWSInstance(configparser)
            username = 'ubuntu'
        time.sleep(30)
        ip_address = instanceObj.getIp()
        print 'IP Address of VM:',ip_address
        inventorystr+='node'+str(index)+' ansible_ssh_host='+ip_address+' ansible_ssh_user='+username+' ansible_ssh_private_key_file='+os.environ['PWD']+'/key/private.key\n'
    with open(os.environ['PWD']+'/inventory', 'w') as inventoryfile:
        inventoryfile.write(inventorystr)
    if os.path.exists(os.environ['PWD']+'/inventory') is False:
        print 'Inventory file '
    print 'Sleeping for 2 mins to allow instance to boot up'
    time.sleep(120)
    # Configure the new virtual instance to run docker
    print os.system('ansible-playbook -i inventory playbook.yml')
    # Store the new redis server's IP into the management redis server
    newredis = redis.StrictRedis(host=ip_address, port=6379, db=0)
    # set the new redis server as a slave to the previous one
    newredis.slaveof(prev_redis_ip,'6379')
    print 'Marked redis at',ip_address,'ass the slave of',prev_redis_ip
    print 'Sleeping for 20 seconds so that sync occurs'
    time.sleep(20)
    r.set('redis_ip',ip_address)
    r.set('redis_url','tcp://'+ip_address+':6379')
    print 'Set redis ip and url in the management database'
    with open('/root/redisenv.env','w') as envfile:
        envfile.write('REDIS_PORT_6379_TCP=tcp://'+ip_address+':6379\n')
    newredis.slaveof('no','one')
    # Executing the docker-compose to shift the ambassador to the new redis server
    process=subprocess.Popen('docker-compose -f /root/docker-compose.yml up -d',stdout=subprocess.PIPE,stderr=subprocess.PIPE,shell=True)
    op = process.communicate()
