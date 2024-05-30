FROM node:18-alpine  
RUN npm install --global prettier 
RUN apk add --no-cache python3 py3-pip 
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
RUN pip install black
WORKDIR /app 
COPY entrypoint.sh /entrypoint.sh 
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"] 