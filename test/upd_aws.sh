#!/bin/bash

for ((i=1; i<=10; i++))
do
    curl -X PUT -d '{"col2": 100, "col3":"UPD_col3", "col4":"POD_UPDATE_col4", "col1": "'$i'"}' -H "Content-Type: application/json" http://$1/users
    echo

    #echo $i
done

