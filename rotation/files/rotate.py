import boto3
from botocore.exceptions import ClientError
import os
from datetime import datetime
import shutil
from ConfigParser import SafeConfigParser

key_file = os.path.join(os.environ['HOME'], 'creds')
access_file = os.path.join(os.environ['HOME'], '.aws', 'credentials')

keys_parser = SafeConfigParser()
keys_parser.read(key_file)
access_parser = SafeConfigParser()
access_parser.read(access_file)

timeStamp =  datetime.fromtimestamp(os.path.getmtime(key_file)).strftime("%b-%d-%y-%H:%M:%S")
key_bak = "%s_%s.bak" % (key_file, timeStamp)

def generate_list_from_parser(parser):
    lst = []
    for profile in parser.sections():
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
        if e.response['Error']['Code'] == 'ParamValidationError':
            raise

def delete_inactive_access_key(user):
    try:
        for access_key in iam.list_access_keys(UserName = user)['AccessKeyMetadata']:
            if access_key['Status'] == 'Inactive':
                # Do we care when the access key was last used before deleting it?
                # response = iam.get_access_key_last_used(AccessKeyId = access_key['AccessKeyId'])
                # Delete the access key.
                print('Deleting access key {0}.'.format(access_key['AccessKeyId']))
                response = iam.delete_access_key(
                    UserName = user,
                    AccessKeyId = access_key['AccessKeyId']
                )
    except ClientError as e:
        raise
        if e.response['Error']['Code'] == 'InvalidClientTokenId':
            print "Not authorized to perform iam maintainence"

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

def write_creds(profile, keyid, secret, keyfile):
    keys_parser.set(profile, 'aws_access_key_id', keyid)
    keys_parser.set(profile, 'aws_secret_access_key', secret)
    with open(keyfile, 'wb') as configfile:
        keys_parser.write(configfile)

#### This should be the start of the main function ####
# first create backup
shutil.copy(key_file, key_bak)

# Target one or all the profiles?
if os.getenv("AWS_PROFILE"):
    profiles = os.environ["AWS_PROFILE"]
    profiles = [profiles]
else:
    profiles = generate_list_from_parser(keys_parser)

# 1. For each profile in AWS credentials, get user.
access = generate_list_from_parser(access_parser)
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
    if find_user(key):
        user = find_user(key)
    else:
        print "Not rotating %s. Moving on..." % key
        continue
    # 2. Can we add a key for this user?  If not, delete the inactive one
    if num_keys() == 2:
        print "User " + user +" in "+ p +" account " + "has this many keys:", num_keys() # num_keys debugging
        try:
            delete_inactive_access_key(user)
        except:
            print "Cannot delete inactive access key for " + user
            continue
    # 3. Add a secondary key for the users we can add keys to
    creds = create_access_key(user)
    print "Created: " + creds[0] + " in: " + p
    # 5. deactivate the original keys for each user
    update_access_key(key, user)
    print "Successfully deactivated " + key + " in " + p
    # 6. rotate user and secret of each profile
    print "Writing creds to " + key_file + "..."
    write_creds(p, creds[0], creds[1], key_file)
