# Set up PostgreSQL and TimescaleDB locally or on a remote lab machine

[Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Start Day 01](day01.md)

This tutorial gives you a separate database for learning SQL. Choose your own computer or a remote test machine reached through SSH. Both routes use the same [course Compose file](compose.yaml), database `brickts_course`, synthetic fixture, and checks. The existing application database remains a separate service.

**Execution status:** These are learner-run instructions. On 2026-10-15, a read-only inspection of `mintbench` observed Python 3.12.3 and Docker Compose 2.40.3. The bench audit inspected remote metadata only. The remote course installation, image pull, database load, and backup procedure below had not been executed on that machine. Record your actual results as you work; an expected result in this page is not an observed remote result.

## Choose where the server runs

| Choice | Where PostgreSQL runs | Where you type SQL | What you need |
| --- | --- | --- | --- |
| Local course Compose | A dedicated container on your computer | Local terminal; the helper uses the container's `psql` | Docker Engine/Desktop, Compose plugin, Python 3 |
| Remote course Compose, SSH terminal | A dedicated container on the test machine | A terminal opened with `ssh mintbench` | SSH access, Docker/Compose and Python 3 on the test machine |
| Remote course Compose, local SQL client | The same remote course container | A local `psql` through an SSH tunnel | The previous route, plus a local PostgreSQL client |
| Existing bench database managed by a DBA | An existing PostgreSQL installation | A client configured by its owner | A new dedicated course database and role; see [the existing-server route](LAB_GUIDE.md#route-b--existing-postgresqltimescale-server-on-the-bench) |

If you are new to both SSH and databases, start with local Compose or use the remote SSH terminal route. You can add the local-client tunnel later. TimescaleDB is a PostgreSQL extension; the container supplies PostgreSQL and the extension together. The early course uses ordinary PostgreSQL SQL; Timescale-specific exercises begin in week 10. See the [official Timescale installation overview](https://www.tigerdata.com/docs/get-started/choose-your-path/install-timescaledb) for the container model.

A **host** is the computer running Docker. A **container** is the isolated database process and its filesystem view. A **volume** retains database files across container restarts. A **client** sends SQL to the server. A schema such as `course` or `student` is a namespace inside `brickts_course`.

## Check prerequisites before installing anything

Run these on whichever computer will host the course container:

```bash
python3 --version
docker version
docker compose version
docker context show
```

`docker version` should show both a client and a reachable server. `docker compose version` must work with a space between `docker` and `compose`; an old standalone `docker-compose` executable alone is insufficient. Confirm the Docker context refers to the intended host. A context pointing to another server would start the lab there.

If Docker is already working, proceed. If it is absent, follow the current official instructions for [Docker Desktop](https://docs.docker.com/get-started/get-docker/) or [Docker Engine on Linux](https://docs.docker.com/engine/install/). If Engine exists but the plugin is missing, use the [Compose plugin installation instructions](https://docs.docker.com/compose/install/linux/). Installation changes belong to the owner of the test machine; this course does not require a general OS upgrade or another application installation.

On Linux, inspect the actual distribution before choosing packages:

```bash
cat /etc/os-release
uname -m
```

Docker documents supported Ubuntu releases and architectures, and explicitly distinguishes Ubuntu derivatives such as Linux Mint. On a Mint bench, have its administrator select the appropriate installation method and supported Ubuntu base rather than putting a Mint release name into an Ubuntu package repository. Do not rerun Docker installation scripts or replace a working engine just to follow a tutorial. See [Docker's Ubuntu prerequisites](https://docs.docker.com/engine/install/ubuntu/).

The helper runs Docker as your normal login user. Docker group membership can allow this, but that group grants root-level control of the host; it is not an ordinary low-privilege database permission. Have the machine owner choose an approved Docker access method, then reconnect and repeat the version checks. See [Docker's Linux access guidance](https://docs.docker.com/engine/install/linux-postinstall/). Do not solve a denied Docker socket by making it world-writable.

The course container is capped at 768 MiB and 1 CPU. Check that the host has capacity for that lab plus its existing workloads. The repository pins an image digest validated as PostgreSQL 16.15 / TimescaleDB 2.30.2 on Linux amd64; another CPU architecture needs an explicitly checked compatible image. Record actual versions with `doctor` after startup.

## Route A: start the database on your computer

**Run locally, from the repository root.** You should see the `lessons/sql` directory here. The launcher uses Python's standard library, so this SQL setup does not require installing the application's Python dependencies or running `uv sync`.

```bash
umask 077
export COURSE_MODE=docker
python3 lessons/sql/lab.py up
python3 lessons/sql/lab.py doctor
python3 lessons/sql/lab.py load
python3 lessons/sql/lab.py check
python3 lessons/sql/lab.py psql
```

`up` starts Compose project `brickts-sql-course` and waits for database health. The first image download may take time. The helper generates a random course password at `var/sql-course/password`, creates that file with permissions `0600`, and passes it to Compose. Keep that private file: changing it does not automatically change the password already stored in an initialized database volume.

The host binding is `127.0.0.1:15432`, forwarded to port `5432` inside this container. The loopback address means clients on other computers cannot use this host port directly. Preserve that binding; there is no reason to publish database port 5432 to the LAN for this course.

In the SQL client, verify where you landed:

```sql
SELECT current_database(), current_user;
SHOW server_version;
SELECT extversion FROM pg_catalog.pg_extension WHERE extname = 'timescaledb';
```

Expect `brickts_course` and the disposable container account `learner`. Use `\q` to return to the terminal. Continue with [the success checks](#success-checks-for-either-route) or [Day 01](day01.md).

## Route B: prepare a dedicated remote course directory

The example SSH alias is `mintbench`. It is a local SSH configuration choice, not a name to embed in SQL. Substitute your own authorized test-machine alias if needed. Confirm the SSH host key through your normal trusted process on first connection.

**Run locally:**

```bash
ssh mintbench
```

**Now run on the remote machine:**

```bash
hostname
whoami
python3 --version
docker version
docker compose version
docker context show
ss -ltn 'sport = :15432'
docker ps --filter label=com.docker.compose.project=brickts-sql-course
```

Confirm this is the intended test machine and that Docker targets its own local daemon. A listener on 15432 or an existing course project needs inspection before proceeding: it may already contain someone's learning work. An empty socket listing and no matching running container are the expected starting conditions for a new course installation. Inspect existing project containers and volumes with the owner as needed; a stopped project can still retain data.

Create the isolated directory on the remote machine:

```bash
umask 077
mkdir -m 700 ~/sparql-playground-course
exit
```

If the directory already exists, `mkdir` stops with an error. Inspect and back up known course work before deciding to reuse it. Do not extract over an unrelated checkout. The `exit` above returns to your local terminal.

### Copy the published course files

**Run locally, from your repository root after the curriculum has been committed.** This export uses files tracked in `HEAD`, not your uncommitted working directory. Verify the required files exist in that revision:

```bash
git rev-parse --short HEAD
git status --short -- lessons/sql
git cat-file -e HEAD:lessons/sql/lab.py
git cat-file -e HEAD:lessons/sql/compose.yaml
```

If `cat-file` fails, use a revision containing the published curriculum before continuing. If `git status` shows your own course edits, decide whether you need them separately; this procedure deliberately exports the committed teaching version.

```bash
umask 077
course_export_dir=$(mktemp -d)
git archive --format=tar --output="$course_export_dir/course-source.tar" HEAD lessons/sql
tar -tf "$course_export_dir/course-source.tar"
```

Read the archive listing before the copy. It should contain only the public `lessons/sql/` tree. Selecting that tree excludes the repository's `.git`, `.venv`, root `var`, application state, and private credential directories. No password file, `.env`, private key, or secrets directory belongs in the teaching tree; stop if you see one. Do not substitute a recursive copy of your whole working directory. The temporary export is not a backup of your student database.

After checking the listing, copy the archive:

```bash
scp "$course_export_dir/course-source.tar" mintbench:sparql-playground-course/course-source.tar
```

**Run locally to reconnect, then run the remaining commands remotely:**

```bash
ssh mintbench
cd ~/sparql-playground-course
tar -tf course-source.tar
tar -xf course-source.tar
python3 lessons/sql/lab.py --help
```

The resulting layout includes `~/sparql-playground-course/lessons/sql/lab.py` and its SQL files. No repository clone, `.git` directory, Python virtual environment, application installer, or source application configuration is needed for this SQL launcher.

### Start and load the remote course container

**Run on the remote machine, from `~/sparql-playground-course`:**

```bash
umask 077
export COURSE_MODE=docker
python3 lessons/sql/lab.py up
python3 lessons/sql/lab.py doctor
python3 lessons/sql/lab.py load
python3 lessons/sql/lab.py check
python3 lessons/sql/lab.py psql
```

These commands create course state under this directory's `var/sql-course` and a dedicated Compose volume. They do not attach to an existing application database. `load` creates the course schemas and inserts missing fixture identities; it does not drop or reset an edited fixture. Keep experiments in `student`.

The exported folder is sufficient for SQL labs. Week 8's offline graph helper imports the playground package and RDFLib: run those graph exercises from your full local checkout after `uv sync --frozen`, or deliberately install that full environment on a separate development machine. The SQL-only archive does not bundle those Python dependencies.

This `psql` runs inside the remote course container. SQL you type reaches that database, and output returns through your SSH terminal. You can complete the course this way without a local PostgreSQL client or any password transfer.

After startup, another remote terminal can check the host listener with `ss -ltn 'sport = :15432'`. Expect loopback `127.0.0.1:15432`, not `0.0.0.0:15432` or a LAN address. Keep the Compose port mapping as supplied. The isolated Compose project name and private host port are part of the course boundary.

## Optional: use your local psql through an SSH tunnel

Complete remote setup first. This route uses the same remote database; it does not create a second one. Your local machine needs a PostgreSQL client (`psql --version`), SSH, Python 3, and the course files. Install only the client through your platform's supported package method if absent; no local PostgreSQL service is required.

**Local terminal A: leave this running.**

```bash
ssh -N -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=30 -o ServerAliveCountMax=3 \
  -L 127.0.0.1:15433:127.0.0.1:15432 mintbench
```

The first `127.0.0.1:15433` is your computer's listening endpoint. The second `127.0.0.1:15432` is interpreted on the remote SSH server. The tunnel carries client traffic between them. This keeps local port 15432 available for a separate local course instance. A port-in-use error is a failure to open the tunnel, not evidence of a working remote connection. Closing terminal A or pressing Ctrl+C ends the tunnel; the remote database continues running.

SSH encrypts the network hop to the remote machine, and the database remains reachable only through remote loopback. Database TLS is a separate mechanism. A directly networked PostgreSQL service needs its own approved TLS/certificate and access configuration; this tutorial does not expose such a service. See [PostgreSQL's SSH tunnel guidance](https://www.postgresql.org/docs/16/ssh-tunnels.html) and [TLS documentation](https://www.postgresql.org/docs/16/ssl-tcp.html).

**Local terminal B, from the repository root:**

```bash
export COURSE_MODE=native
export PGHOST=127.0.0.1
export PGPORT=15433
export PGDATABASE=brickts_course
export PGUSER=learner
export PGSSLMODE=disable
unset PGPASSWORD
```

Here `native` means the helper launches your local `psql`; it does not mean the database was installed directly on the remote OS. `PGSSLMODE=disable` applies to this loopback client connection protected by the SSH tunnel. Do not carry it into a direct network connection. Libpq's `PG*` settings select the endpoint and account; see its [environment variable reference](https://www.postgresql.org/docs/16/libpq-envars.html).

### Store the course password privately

The generated remote password remains in the remote course directory. For local helper commands, create a dedicated local password file rather than placing a password in a command, URL, SQL file, or transcript. PostgreSQL accepts the private file named by `PGPASSFILE`; on Unix it ignores a password file accessible to other users. See [the password file format and permissions](https://www.postgresql.org/docs/16/libpq-pgpass.html).

The following optional script reads the remote course password over SSH into memory and writes only the private local file. It does not display the password, put it in process arguments, or overwrite an existing file. Run it in your own terminal with shell tracing disabled. Use the same authorized SSH account and remote course directory as above.

```bash
umask 077
mkdir -p "$HOME/.config/brickts-sql-course"
chmod 700 "$HOME/.config/brickts-sql-course"
export PGPASSFILE="$HOME/.config/brickts-sql-course/pgpass"
python3 - <<'PY'
import os
import subprocess

password = subprocess.check_output(
    ['ssh', 'mintbench', 'cat',
     'sparql-playground-course/var/sql-course/password'],
    text=True,
).strip()
if not password:
    raise SystemExit('No course password was read; no local file created.')
escaped = password.replace('\\', '\\\\').replace(':', '\\:')
fd = os.open(os.environ['PGPASSFILE'], os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, 'w') as handle:
    handle.write('127.0.0.1:15433:brickts_course:learner:' + escaped + '\n')
print('Created the private course password file; password not displayed.')
PY
```

If the file already exists, inspect its ownership and connection purpose privately before changing it. Keep it outside Git and screenshots. A changed tunnel port or account needs a matching entry; a stopped tunnel is not a password problem.

Now verify and use the remote database from local terminal B:

```bash
psql -X -v ON_ERROR_STOP=1 -c 'SELECT current_database(), current_user;'
python3 lessons/sql/lab.py doctor
python3 lessons/sql/lab.py check
python3 lessons/sql/lab.py psql
```

Native `up` and `down` are deliberately refused; manage the remote course container in the remote SSH terminal. Saved SQL passed to native `run` is read from your local filesystem, then sent to the remote database. Use the local course revision that matches the remote fixture.

## Success checks for either route

Run `check` using the route you chose. It verifies fixture contracts and bounded engineering examples. A fresh fixture should have 2 sites, 3 AHUs, 42 points, and 24,190 stored samples. There is one bad/null power observation and two entirely absent pressure observations. An expected total is useful only when the check actually completes successfully.

In `psql`, inspect both identity and totals:

```sql
SELECT current_database(), current_user;
SELECT count(*) AS sites FROM course.site;
SELECT count(*) AS equipment FROM course.equipment;
SELECT count(*) AS points FROM course.point;
SELECT count(*) AS stored_samples,
       count(value) AS non_null_samples
FROM course.sample;
```

Expect sample counts `24190` and `24189`. Save the server/extension versions, source revision, chosen route, and check status without secrets. The known-answer fault reference also expects 3,000 raw, 1,800 confirmed, and 600 unknown seconds for its declared teaching window and confirmation convention. These are synthetic fixture checks, not claims about a real building or the complete production FC1 implementation.

The Docker-created account `learner` is the bootstrap administrator, normally a superuser in this image. Verify the actual flags rather than treating its name as evidence of limited access:

```sql
SELECT rolname, rolsuper, rolbypassrls
FROM pg_catalog.pg_roles
WHERE rolname = current_user;
```

Its successful queries do not establish restricted reader permissions or RLS isolation. Week 4 examines that distinction.

## Optional DBA task: a restricted report reader

A separate reader is useful after the basic lab works. This is an optional task for the owner of the dedicated course server, not a prerequisite for beginner exercises that create scratch tables. Review existing names and privileges before executing any role DDL. In an authorized administrator session on the course server, the following illustrates a full-course, read-only reporting account:

```sql
\connect brickts_course
SELECT current_database();
CREATE ROLE course_reader LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;
\password course_reader
GRANT CONNECT ON DATABASE brickts_course TO course_reader;
GRANT USAGE ON SCHEMA course TO course_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA course TO course_reader;
ALTER DEFAULT PRIVILEGES FOR ROLE learner IN SCHEMA course
    GRANT SELECT ON TABLES TO course_reader;
```

`\password` prompts without putting the password into SQL history. Default privileges here concern future tables made by `learner`, not every possible owner. This role is allowed to read the synthetic course across both sites; it is not a tenant-isolation policy. Verify allowed reads and denied writes in a separate connection with that identity. Do not give it `learner` membership, Docker access, or server administration just to make a check pass. A reader also cannot complete the course's scratch DDL exercises without a separately designed writer role.

## Back up remote learning work without resetting anything

**Run remotely from `~/sparql-playground-course`, with `COURSE_MODE=docker`.** A retained Docker volume survives container replacement, but it is not a backup. The following makes a timestamped custom-format dump of only `brickts_course`, including `student` work. It invokes the `pg_dump` bundled with the course container, so the client major version matches its server. See [PostgreSQL's pg_dump reference](https://www.postgresql.org/docs/16/app-pgdump.html).

The script reuses the launcher's private environment construction instead of displaying the Compose password. The archive is written under the ignored, private `var/sql-course/backups` directory. It verifies that `pg_restore` can read the archive catalogue; a full restore remains a separate test in another disposable database.

```bash
umask 077
export COURSE_MODE=docker
python3 - <<'PY'
from datetime import datetime, timezone
from pathlib import Path
import os
import runpy
import subprocess

lab = runpy.run_path('lessons/sql/lab.py')
env = lab['environment']()
lab['require_course_database'](env)
backup_dir = Path('var/sql-course/backups')
backup_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
os.chmod(backup_dir, 0o700)
stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
archive = backup_dir / f'brickts_course-{stamp}.dump'
compose = lab['compose']()
with archive.open('xb') as output:
    subprocess.run(
        compose + ['exec', '-T', 'db', 'pg_dump', '-U', 'learner',
                   '-d', 'brickts_course', '-Fc'],
        env=env, stdout=output, check=True,
    )
with archive.open('rb') as source:
    subprocess.run(
        compose + ['exec', '-T', 'db', 'pg_restore', '--list'],
        env=env, stdin=source, stdout=subprocess.DEVNULL, check=True,
    )
print(f'Created {archive}; archive catalogue readable. Full restore not tested.')
PY
```

A nonzero exit is a failed backup attempt even if a partial file exists. Keep the original database and previous successful backups. Copy a selected successful archive to a private location on another machine if you need protection from host loss; inspect the exact timestamped name first. Never commit dumps or treat a backup as permission to wipe a volume. Do not restore over an application database or use production data in this lab.

## Stop, resume, and diagnose

To stop the course container while retaining its volume, run this on the host that runs the container:

```bash
export COURSE_MODE=docker
python3 lessons/sql/lab.py down
```

Resume with `up`, then `doctor` and `check`. An SSH disconnection or closed tunnel does not stop the database. Preserve the course password file and volume together. Do not add `-v`, delete volumes, prune Docker state, or recreate an unrelated service to resolve a lesson error.

| Symptom | First check |
| --- | --- |
| `docker compose` is unavailable | Verify the Compose plugin with the machine owner; a legacy executable is a different command. |
| Docker socket permission denied | Check the approved Docker access method and reconnect after any authorized membership change. |
| Port 15432 is occupied | Identify the listener and existing course project; choose an explicit alternate course port only after understanding the conflict. |
| SSH tunnel cannot bind 15433 | Check local listeners; if you choose another local port, update `PGPORT` and the password-file entry together. |
| Connection refused from local psql | Check terminal A's tunnel and the remote course container's health. |
| Password authentication fails | Check endpoint, account, and private file match; do not print passwords or regenerate the stored file blindly. |
| Database guard rejects the target | Inspect `PGDATABASE` and `\conninfo`; the required database is `brickts_course`. |
| Fixture check fails after a lesson | Inspect your known edits and transaction state; keep experiments in `student` and restore deliberately. |

## Completion checklist

- [ ] I can name the computer running PostgreSQL, the client location, and the chosen connection route.
- [ ] Docker and Compose work in the intended context, and actual server/extension versions are recorded.
- [ ] The course uses its dedicated project, directory, volume, and `brickts_course` database.
- [ ] The database host port binds only to loopback; no database port was opened to the LAN.
- [ ] `load` and `check` completed successfully, with the expected 2 / 3 / 42 / 24,190 inventory.
- [ ] Secrets and backups remain private and outside Git; tunnel credentials are not in command history.
- [ ] I understand that `learner` is a disposable lab administrator and does not prove reader isolation.
- [ ] I can stop/resume the lab without deleting its volume, and I have recorded whether a backup or restore was actually tested.

[Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Start Day 01](day01.md)
