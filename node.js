#!/bin/bash

// Setup nodejs
sudo -s
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.34.0/install.sh | bash   
chmod 755 /.nvm/nvm.sh
. /.nvm/nvm.sh
nvm install node
node -e "console.log('Running Node.js ' + process.version)"

cat <<EOF> package.json
{
    "name": "my-app",
    "version": "0.0.1",
    "private": true,
    "dependencies": {
      "express": "latest",
      "mariadb": "latest",
      "mysql": "latest"
    },
    "scripts": {
      "start": "node index.js"
    }
}
EOF

npm install

// Setup index.js
cat <<EOF> index.js
const express = require('express');
const os = require('os');
const mariadb = require('mysql');
const app = express();
const port = 80;
 
app.use(express.json());
 
const {
  DB_HOST,
  DB_USER,
  DB_PASSWORD,
  DB_DATABASE
} = process.env;                                                                
 
// db configuration
const client = mariadb.createPool({
  host     : 'your host',
  port     : 3306,
  user     : 'admin',
  password : `{DB_PASSWORD}`,
  database : 'adt',
  connectionLimit: 20
});
 
//console.log(`Running query to MariaDB server: ` + `${DB_HOST}`);
 
// basic endpoint
app.get('/', (req, res) => {
  res.send('Application started successfully: ' + os.hostname() + '\n');
})
 
// health check endpoint
app.get('/health', (req, res) => {
  client.query('SELECT NOW()', (err, results) => {
    res.status(200).json({ Database_is_up_and_running: results[0] });
  });
})
 
// get user by id
app.get('/users', (req, res) => {
  const { col1 } = req.body
  //console.log('Get user col1 = ' + col1);
  client.query('SELECT * FROM tab1 WHERE col1 = ?', [col1], function(err, results) {
    res.status(200).json({ Info: results[0] });
  });
})
 
// save new user
app.post('/users', (req, res) => {
  //console.log('Saving new user');
  const { col1, col2, col3, col4 } = req.body
  //console.log('Post user col1 = ' + col1, col2, col3, col4);
  client.query('INSERT INTO tab1 VALUES (?, ?, ?, ?)', [col1, col2, col3, col4], function(err, results) {
    res.status(200).json({ affectedRows: results.affectedRows });
  });
})
 
// update user by id
app.put('/users', (req, res) => {
  const { col2, col3, col4, col1 } = req.body
  //console.log('Update user col1 = ' + col1);
  client.query('UPDATE tab1 SET col2 = ?, col3 = ?, col4 = ? WHERE col1 = ?', [col2, col3, col4, col1], function(err, results) {
    res.status(200).json({ affectedRows: results.affectedRows });
  });
})
 
// delete user by id
app.delete('/users', (req, res) => {
  const { col1 } = req.body
  //console.log('Delete user col1 = ' + col1);
  client.query('DELETE FROM tab1 WHERE col1 = ?', [col1], function(err, results) {
    res.status(200).json({ affectedRows: results.affectedRows });
  });
})
 
app.listen(port, () => {
    console.log(`Application listening on port ${port}`)
});
EOF

nohup node index.js &

// Setup mariadb client
tee /etc/yum.repos.d/mariadb.repo<<EOF
[mariadb]
name = MariaDB
baseurl = http://yum.mariadb.org/10.5/centos7-amd64
gpgkey=https://yum.mariadb.org/RPM-GPG-KEY-MariaDB
gpgcheck=1
EOF

yum makecache
yum install MariaDB-client -y
// mysql -h your_host -u admin -p
