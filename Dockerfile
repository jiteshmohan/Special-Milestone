FROM ubuntu

RUN apt-get update
RUN apt-get -y install nodejs npm; ln -s /usr/bin/nodejs /usr/bin/node
COPY ./app/ /src/
RUN cd /src/; npm install 

CMD nodejs /src/app.js
