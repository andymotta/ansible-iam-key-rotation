import boto3
from botocore.exceptions import ClientError
import logging
import os
from datetime import datetime
import shutil
from ConfigParser import SafeConfigParser

logging.basicConfig()
logger = logging.getLogger()

key_file = os.path.join(os.environ['HOME'], 'creds')
access_file = os.path.join(os.environ['HOME'], '.aws', 'credentials')

parser = SafeConfigParser()
parser.read(key_file)
access_list = SafeConfigParser()
access_list.read(access_file)

timeStamp =  datetime.fromtimestamp(os.path.getmtime(key_file)).strftime("%b-%d-%y-%H:%M:%S")
key_bak = "%s_%s.bak" % (key_file, timeStamp)

def generate_profile_list():
    lst = []
    for profile in parser.sections():
        lst.append(profile)
    return lst

def generate_access_list():
    lst = []
    for profile in access_list.sections():
        lst.append(profile)
    return lst

def get_aws_access_key_id(profile):
    return parser.get(profile, 'aws_access_key_id')

def find_user(key):
    try:
        key_info = iam.get_access_key_last_used(AccessKeyId=key)
        return key_info['UserName']
    except ClientError as e:
        if e.response['Error']['Code'] == 'AccessDenied':
            print "%s does not exist in target account" % key
            return False

def num_keys():
    # See if IAM user already has more than one key
    paginator = iam.get_paginator('list_access_keys')
    try:
        for response in paginator.paginate(UserName=user):
            return len(response['AccessKeyMetadata'])
    except ClientError as e:
        logger.error("Received error: %s", e, exc_info=True)
        if e.response['Error']['Code'] == 'ParamValidationError':
            raise

# Create an access key
def create_access_key(user):
    try:
        response = iam.create_access_key(
            UserName=user
        )
        AccessKey = response['AccessKey']['AccessKeyId']
        SecretAccessKey = response['AccessKey']['SecretAccessKey']
        return AccessKey, SecretAccessKey
    except ClientError as e:
        logger.error("Received error: %s", e, exc_info=True)
        if e.response['Error']['Code'] == 'LimitExceededException':
            print "User already has two keys, cannot add more"

# Change state of first access key to inactive before deleting
# this should only tru to update users with one key
def update_access_key(key, user):
    iam.update_access_key(
            AccessKeyId=key,
            Status='Inactive',
            UserName=user
        )

def write_creds(profile, keyid, secret):
    parser.set(profile, 'aws_access_key_id', keyid)
    parser.set(profile, 'aws_secret_access_key', secret)
    # Writing our configuration file to 'example.ini'
    with open(key_file, 'wb') as configfile:
        parser.write(configfile)

#### This should be the start of the main function ####
# first create backup
shutil.copy(key_file, key_bak)

# 1. For each profile in AWS credentials, get user.
profiles = generate_profile_list()
access = generate_access_list()
keys = []
for p in profiles:
    if p == 'default':
        continue
    if p not in access:
        print "Not rotating %s profile, no access." % p
        continue
    key = get_aws_access_key_id(p)
    if key in keys: # Don't do this twice if default is the same key as some other profile
        print "Will not rotate %s, list duplicate." % p
        continue
    keys.append(key)
    # create a custom session to taget account based on profile
    os.environ["AWS_PROFILE"] = p
    session = boto3.session.Session()
    iam = session.client('iam')
    # Get the user from the key on the host
    user = find_user(key)
    # 2. Can we add a key for this user?  If yes, create key.  If not, log.
    if num_keys() == 2:
        print "Cannot add more keys for " + user + " " + key
        continue
    print p +": " + key + " " + user, num_keys()
    # 3. Add a secondary key for the users we can add keys to
    creds = create_access_key(user)
    print "Created: " + creds[0] + "in: " + p
    # 5. deactivate the original keys for each user
    update_access_key(key, user)
    print "Successfully deactivated " + key + " in " + p
    # 6. rotate user and secret of each profile
    print "Writing creds to " + key_file + "..."
    write_creds(p, creds[0], creds[1])
