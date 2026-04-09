Place the Hermes host-SSH files for this project in this directory.

This directory is mounted read-only into the Hermes container at `/root/.ssh`.
Hermes is configured to use `/root/.ssh/id_rsa` from `settings/hermes/config.yaml`.
The SSH user, port, and working directory come from `.env`.

Expected files:
- `id_rsa`
- `id_rsa.pub`
- `known_hosts`

How to create these files on a new server:

1. Make sure the host is running `sshd` and that the target account can SSH to itself.
   Example check:
   `ssh -o BatchMode=yes localhost whoami`

2. If the host does not already have a keypair, create one for the account Hermes will use.
   Example:
   `ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa`

3. Authorize that key for the same user on the host.
   If needed:
   `cat ~/.ssh/id_rsa.pub >> ~/.ssh/authorized_keys`
   `chmod 600 ~/.ssh/authorized_keys`

4. Copy the private and public key into this folder.
   Example:
   `install -d -m 700 ./secrets/ssh`
   `install -m 600 ~/.ssh/id_rsa ./secrets/ssh/id_rsa`
   `install -m 644 ~/.ssh/id_rsa.pub ./secrets/ssh/id_rsa.pub`

5. Generate a `known_hosts` entry for the hostname used inside Docker.
   Hermes connects to `host.docker.internal`, not `localhost`, so rewrite the scanned host key to that name:
   `{
     printf '# Generated from local host SSH daemon for Docker Hermes\n'
     ssh-keyscan -t rsa,ed25519 localhost 2>/dev/null | sed 's/^localhost /host.docker.internal /'
   } > ./secrets/ssh/known_hosts`
   `chmod 644 ./secrets/ssh/known_hosts`

6. Recreate Hermes after changing these files:
   `docker compose up -d --build --force-recreate hermes`

Verification:

- Check the files are visible inside the container:
  `docker compose exec hermes ls -la /root/.ssh`
- Check SSH to the host works from the container:
  `docker compose exec hermes sh -lc 'ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o UpdateHostKeys=no -i /root/.ssh/id_rsa ${HERMES_HOST_SSH_USER}@host.docker.internal whoami'`

Expected result:
- `whoami` should print the host account name.
- `pwd` over the same SSH path should show a host path like `/home/<user>`.

Notes:
- Keep private keys out of version control.
- `id_rsa` should be mode `600`.
- `known_hosts` is intentionally project-local so this stack stays self-contained.
- If you change the SSH host or key path, update `settings/hermes/config.yaml` to match.
- If you change the SSH user, port, or working directory, update `.env` and recreate Hermes.
