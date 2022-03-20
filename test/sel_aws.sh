#!/bin/bash
 
#for ((i=1; i<=100000; i++))
for ((i=1; i<=10; i++))
do
  curl -X GET -d '{"col1": "'$i'" }' -H "Content-Type: application/json" http://$1/users
  echo
	     
  #echo $i
done
