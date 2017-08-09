# ansible-iam-key-rotation

This is a Boto3 Script to rotate AWS IAM keys on EC2 targets with an Ansible wrapper for use with dynamic inventory.

The scripts assumes the Ansible control node has admin keys with privileges to rotate remote/target IAM keys.  It will loop through profiles on the control node for access, and look for matching profiles on the target node for rotation.

For example,  if the control node has the profile prod and the target node also has a profile named prod, those keys will be rotated as long as the control node has an admin policy for  IAM control.  Access is not required on the target.

Because of this behaviour, we can change *hosts* to **localhost** to target the local `~/.aws/credentials` for both rotation and access.

Usage
----------------
(Dynamic Inventory)
```yml
- name: Rotate keys on target hosts
  hosts: "tag_Name_{{ resource_name }}"
  gather_facts: true
  become: true
  become_user: root
  roles:
    # IAM Key Rotation
    - { role: rotation, tags: rotation }
```

### Variables
Defaults can be overridden at any level
- *dest_home_dir*: The home dir of the remote credentials file being targeted for rotation.  Local destination is OK.
- *dest_owner*: Owner permissions of the credentials file
- *dest_group*: Group permissions of the credentials file
