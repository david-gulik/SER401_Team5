apt-get -y install openjdk-11-jdk python3-pip

# The following lines are to make sure we can install packages from maven
# See https://bugs.launchpad.net/ubuntu/+source/ca-certificates-java/+bug/1396760
# and https://github.com/docker-library/openjdk/issues/19#issuecomment-70546872
apt-get install --reinstall ca-certificates-java
update-ca-certificates -f

#RA: manually fetch maven 3.8.9 instead of using default 3.5.0 package
cd /autograder
wget https://mirror.olnevhost.net/pub/apache/maven/maven-3/3.8.9/binaries/apache-maven-3.8.9-bin.tar.gz
tar xzvf apache-maven-3.8.9-bin.tar.gz

#RA: install jh61b manually
cd /autograder/source
export PATH="/autograder/apache-maven-3.8.9/bin:$PATH"
mvn install:install-file -Dfile=lib/jh61b-1.0.jar

# cache maven packages and plugins during Docker build
mvn dependency:go-offline

# install packages for shoggoth
pip3 install -r requirements.txt