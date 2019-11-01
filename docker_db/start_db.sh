#!/bin/bash
./build.sh $1
sudo rm -rf volume/
mkdir $(pwd)/volume
docker run --name mysql-$1 -v $(pwd)/volume:/var/lib/mysql -p 3306:3306 -d $1