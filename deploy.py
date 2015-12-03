import argparse
import subprocess, json, redis, time

def build_image(img_name, docker_file, imagevar):
    cmd = 'docker build -t '+img_name+' --file '+docker_file+' .'
    process = subprocess.Popen(cmd,stdout=subprocess.PIPE, shell=True)
    process.communicate()
    redisclient.set(imagevar,img_name)

def start_container(img_name, containername, containervar, portvar):
    cmd = 'docker run -p 8080:5000 --name '+containername+' --env-file appenv.env --link redis_ambassador:redis -d '+img_name
    process = subprocess.Popen(cmd,stdout=subprocess.PIPE, shell=True)
    process.communicate()
    redisclient.set(containervar,containername)
    # Store the port number
    cmd = 'docker port '+containername
    process = subprocess.Popen(cmd,stdout=subprocess.PIPE, shell=True)
    redisclient.set(portvar,process.communicate()[0].strip().split(':')[1])

def stop_container(containername):
    # stop previous container
    cmd = 'docker stop '+containername
    process = subprocess.Popen(cmd,stdout=subprocess.PIPE, shell=True)
    process.communicate()
    # delete previous container
    cmd = 'docker rm '+containername
    process = subprocess.Popen(cmd,stdout=subprocess.PIPE, shell=True)
    process.communicate()                    

def delete_image(img_name):
    cmd = 'docker rmi '+img_name
    process = subprocess.Popen(cmd,stdout=subprocess.PIPE, shell=True)
    process.communicate()

def returnimgname(currimagename, imgtype):
    if (imgtype=='prod'):
        if currimagename==None:
            return ['nc-prod-img','nc-prod-img0']
        elif (currimagename=='nc-prod-img'):
            return ['nc-prod-img','nc-prod-img0']
        else:
            return ['nc-prod-img0','nc-prod-img']
    if (imgtype=='canary'):
        if currimagename==None:
            return ['nc-canary-img','nc-canary-img0']
        elif (currimagename=='nc-canary-img'):
            return ['nc-canary-img','nc-canary-img0']
        else:
            return ['nc-canary-img0','nc-canary-img']

def returncontainername(currcontname, imgtype):
    if (imgtype=='prod'):
        if currcontname==None:
            return ['nc-prod-cont','nc-prod-cont0']
        elif (currimagename=='nc-prod-img'):
            return ['nc-prod-cont','nc-prod-cont0']
        else:
            return ['nc-prod-cont0','nc-prod-cont']
    if (imgtype=='canary'):
        if currimagename==None:
            return ['nc-canary-cont','nc-canary-cont0']
        elif (currimagename=='nc-canary-img'):
            return ['nc-canary-cont','nc-canary-cont0']
        else:
            return ['nc-canary-cont0','nc-canary-cont']

if __name__=="__main__":
    parser = argparse.ArgumentParser(description="Creates images for production and canary apps and then start containers.")
    parser.add_argument('--server',dest='servertype',required=True,type=str,nargs='?',choices=['production','canary'],help='Choose the type of server to deploy as a container.')
    args = parser.parse_args()

    redis_img_name = 'redis-img'
    redis_cont_name ='redis'
    prod_img_name_def = 'nc-prod-img'
    canary_img_name_def = 'nc-canary-img'
    prod_cont_name_def = 'nc-prod-cont'
    canary_cont_name_def = 'nc-can-cont'
    nextprodimagename = str()
    nextcanaryimagename = str()
    nextprodcontainername = str()
    nextcanarycontainername = str()

    # Check if redis image already exists
    cmd = 'docker images '+redis_img_name
    process = subprocess.Popen(cmd,stdout=subprocess.PIPE, shell=True)
    redisimage = process.communicate()[0].strip().split('\n')[1:]
    # Create redis image if it does not already exist
    if (len(redisimage)==0):
        cmd = 'docker build -t '+redis_img_name+' --file redis-dockerfile .'
        process = subprocess.Popen(cmd,stdout=subprocess.PIPE, shell=True)
        print process.communicate()[0]

    # Check if redis container already exists
    cmd = 'docker ps --filter name='+redis_cont_name
    process = subprocess.Popen(cmd,stdout=subprocess.PIPE, shell=True)
    containers = process.communicate()[0].strip().split('\n')[1:]
    # Create redis container if it is absent
    if (len(containers)==0):
        cmd = 'docker run -p 6379 --name '+redis_cont_name+' -d '+redis_img_name
        process = subprocess.Popen(cmd,stdout=subprocess.PIPE, shell=True)

    # Connecting to redis server
    cmd = 'docker inspect '+redis_cont_name
    process = subprocess.Popen(cmd,stdout=subprocess.PIPE, shell=True)
    inspectop = json.loads(process.communicate()[0].strip())
    gateway = inspectop[0]['NetworkSettings']['Gateway']
    portnum = inspectop[0]['NetworkSettings']['Ports']['6379/tcp'][0]['HostPort']
    redisclient = redis.StrictRedis(host=gateway, port=portnum, db=0)

    if (args.servertype=='production'):
        # Check if redis image already exists
        prod_img_name = redisclient.get('image_prod')
        if (prod_img_name==None): 
            prod_img_name=prod_img_name_def
            build_image(prod_img_name_def, 'prod-dockerfile', 'image_prod')
            start_container(prod_img_name, prod_cont_name_def, 'container_prod', 'prod_port')
            return
        prod_img_name, nextprodimagename = returnimgname(prod_img_name,'prod')
        build_image(nextprodimagename, 'prod-dockerfile', 'image_prod')
        # create new container with above image
        # start container
        prod_cont_name = redisclient.get('container_prod')
        if (prod_cont_name==None): 
            prod_cont_name=prod_cont_name_def
            start_container(nextprodimagename, prod_cont_name_def, 'container_prod', 'prod_port')
            return
        prod_cont_name, nextprodcontainername = returncontainername(prod_cont_name, 'prod')
        start_container(nextprodimagename, nextprodcontainername, 'container_prod', 'prod_port')
        time.sleep(20)
        stop_container(prod_cont_name)
        # delete previous image
        delete_image(prod_img_name)
    if (args.servertype=='canary'):
        # Check if redis image already exists
        canary_img_name = redisclient.get('image_canary')
        if (canary_img_name==None): 
            canary_img_name=canary_img_name_def
            build_image(canary_img_name_def, 'canary-dockerfile', 'image_canary')
            start_container(canary_img_name, canary_cont_name_def, 'container_canary', 'canary_port')
            return
        canary_img_name, nextcanaryimagename = returnimgname(canary_img_name,'canary')
        build_image(nextcanaryimagename, 'canary-dockerfile', 'image_canary')
        # create new container with above image
        # start container
        canary_cont_name = redisclient.get('container_canary')
        if (canary_cont_name==None): 
            canary_cont_name=canary_cont_name_def
            start_container(canary_img_name, canary_cont_name_def, 'container_canary', 'canary_port')
            return
        canary_cont_name, nextcanarycontainername = returncontainername(canary_cont_name, 'canary')
        start_container(nextcanaryimagename, nextcanarycontainername, 'container_canary', 'canary_port')
        time.sleep(20)
        stop_container(canary_cont_name)
        # delete previous image
        delete_image(canary_img_name)
