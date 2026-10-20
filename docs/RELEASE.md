# Making a release

How a new version of MoolaKata reaches testers and households. A release is a `v<version>` tag
on `main` and a GitHub release that names it. The tag starts `.github/workflows/release.yml`
(requirements S17.10.2). It builds both images on an amd64 and an arm64 runner and runs
`web/install/smoke.sh` on each, which is the release gate (S17.8.1). It then pushes the images
to `ghcr.io/mojokata`, joins each image's two architectures under the version's tag, and
attests both images (S17.8.2). Everything before the tag happens in an ordinary pull request.
Everything after it is checking what was published.

The steps were written from 0.1.0's release, made through GitHub's web pages.

## 1. Before you start

- **Write access to `MojoKata/MoolaKata`.** The release and its tag are made there; a fork
  can open the release's pull request but not tag it.
- **[`gh`](https://cli.github.com/)**, signed in, and **Docker** with buildx, to check what
  was published (§7).
- **A checkout set up for development** (`web/dev.sh setup`, README), for the regenerated
  files and `web/check`.
- **Done once, at 0.1.0; don't repeat it.** A new package on ghcr.io starts private. MojoKata's
  **Settings › Packages › Package creation** allows public packages, and both packages,
  `moolakata` and `moolakata-connector`, were made public under each package's **Package
  settings › Change visibility**. Every later version inherits that. A third image would need
  it again.

## 2. Pick the version

MoolaKata uses [semantic versioning](https://semver.org): `MAJOR.MINOR.PATCH` (`1.4.2`),
tagged `v` and the same numbers (`v1.4.2`). `release.yml` refuses a tag that isn't `v`
followed by `web/VERSION`'s text. The tests read `DEPLOY.md`'s image tags as three numbers.

1. **MAJOR**: the release upgrades the database, which means it adds a migration (a new
   revision in `web/server/src/moolakata/store/alembic/versions/`). The server migrates at
   its first unlock. After that an older release refuses the database, so going back means
   restoring the copy made before the upgrade (`operations.md` §3).
2. **MINOR**: new features, with the database left as it was.
3. **PATCH**: fixes alone.

To see whether the database has changed since the last release:

```sh
git diff --stat v0.1.0..upstream/main -- web/server/src/moolakata/store/alembic/versions/
```

**Before 1.0.0**, while releases are for testers, each kind of release moves down one
place, as semantic versioning allows for 0.x. A migration takes the next minor (`0.2.0`), and
anything else takes the next patch (`0.1.1`). 1.0.0 is the first release meant for
households to rely on.

A version is never reused. Browsers keep the app's files for a year under `/ui/v/<version>/`,
and testers may already have pulled the images under that tag. A second build under the same
version would be served stale to the first group and silently replaced for the second.

## 3. The release's pull request

1. **Branch from an up-to-date `main`**: `git switch -c release-0.2.0 main` once `main`
   matches MojoKata's.
2. **Change the version everywhere it is written by hand.** These are `web/VERSION` (the
   server's version, which the app, the API's document and the release workflow all read),
   the connector's `connector/pyproject.toml` and `connector/moolakata_connector/__init__.py`,
   the image tags in the four `web/install/compose*.yaml` files, `docs/DEPLOY.md`,
   `docs/operations.md` and the README's **Release** line. From the repository's root:

   ```sh
   old=$(cat web/VERSION) new=0.2.0
   git grep -lF "$old" -- web/VERSION connector/pyproject.toml connector/moolakata_connector/__init__.py \
       web/install docs/DEPLOY.md docs/operations.md README.md |
     xargs sed -i "s/${old//./\\.}/$new/g"
   git diff --stat        # 10 files
   ```

   Then read the diff for two lines that need a person's judgement:
   - `DEPLOY.md`'s second paragraph says which release its steps were run with. Put the old
     version back there until §8 has run them with the new one.
   - The README's **Release** line still says *a pre-release for testers*. Keep that
     unless this release is meant for households to rely on.

   The `0.1.0`s left in the dev seed (`seed_connector.py`, `seed_links.py`), in the tests and
   in the hand-written mockup are sample data, and stay as they are.
3. **Move the base image** (S17.8.5). Both Dockerfiles pin `python:3.14-slim-bookworm` by
   digest, and the digest moves with each release:

   ```sh
   web/dev.sh base-update --packages
   ```

   It writes the new digest into both Dockerfiles and records the move in `web/audit.json`.
   It also prints the Debian packages that changed, for the commit message and the release
   notes. Bring the base image's row in `docs/dependencies.md` up to date by hand: the date
   it last moved and what the move picked up.
4. **Regenerate what carries the version**: the API's OpenAPI document (S13.8.9), in a few
   seconds, and the generated mockup, in about ten minutes:

   ```sh
   (cd web/server && uv run --frozen python -m moolakata.contract write)   # web/ui/api/openapi.json
   web/dev.sh mockup                                                        # docs/mockups/MoolaKata-app.html
   ```

   The mockup's diff is the version alone, in its `mk-version` meta tag and the recorded
   `/ui/api/session` and `/ui/api/unlock` answers. Anything more means `main` had drifted
   already. Find out why before going on.
5. **Bring every document that goes with the release up to date**, in this same pull
   request. Its documents describe the release from the moment it is tagged. Start from
   what changed since the last release, `git log --oneline v0.1.0..upstream/main`, and
   check each document against it:
   1. **README**: the **Release** line and the **Status** paragraph.
   2. **`docs/DEPLOY.md`**: every step the release changed (a setting, a screen, a port, a
      file), and new screenshots of the screens that now look different. Its second
      paragraph waits for §8.
   3. **`docs/operations.md`**: the runbook for anything the release changed, such as
      upgrading, commands, configuration keys and backups.
   4. **`docs/test-plan.md`**: a test for anything new that the build can't try by itself.
   5. **The app's guides** (`web/ui/guides/`), which ship inside the image. Each screen the
      release changed must still read true. Retake the screenshots of those screens with
      `web/dev.sh help-shots <key> …`.
   6. **`docs/api.md`, `docs/connector-protocol.md` and `docs/link-protocol.md`**: every
      change to the API, the connector's protocol or the link protocol since the last
      release. The release notes say what each change means for a server and a connector,
      or for two linked servers, that are at different releases (§4).
   7. **`docs/dependencies.md`**: the base image's row (step 3), and any library whose
      **Revisit** has come due.
   8. **`docs/requirements/`**: they carry no versions, so nothing changes for the release
      itself. Check that the README's tables of gaps and open questions match what this
      release leaves open.
6. **Run every check**: `web/check`, which takes about 20 minutes, and look for its last line,
   `all checks passed`. A compose file or a `DEPLOY.md` tag left at the old version fails
   `test_install.py`.
   The generated mockup's crawl sometimes fails without a diff: a Playwright route-handler
   error, or a screen that *drew nothing in 20 s*. When that is the only failure, run it
   again alone, `(cd web/server && uv run --frozen python ../ui/mockup/build.py --check)`.
7. **Commit and open the pull request** against `MojoKata/MoolaKata`'s `main`, titled
   `Release 0.2.0`. Because it touches `web/install/`, two workflows run on it: `check`
   (`web/check`, about half an hour) and `release`, which builds both images and smoke-runs
   them on both architectures without pushing anything. A green pull request means the tag
   will build.
8. **Squash-merge it.** Nothing else should merge between this and the tag. If something
   does, the tag goes on the release's commit rather than on `main`'s head (§5).

## 4. The release notes

The notes tell a tester what changed, how to upgrade, and what was tried by hand. Write them
before tagging, so the release page is complete the moment it appears. A starting point:

```markdown
For testers. A new install follows docs/DEPLOY.md; a server you already run upgrades with
DEPLOY.md §6, then unlocks.

## What's new
- (one line for each pull request merged since v0.1.0)

## Upgrading
(A release that upgrades the database:) At its first unlock the server copies its database
to data/pre-upgrade/ and migrates it, and an older release can't open it after that;
docs/operations.md §3 says how to go back. (Any other release:) The database stays as it is.
The connector takes the same version.

## Compatibility
(What a server at this release and a connector or linked server at the last one do
together, or that both must be upgraded.)

## Tried by hand (docs/test-plan.md)
Run: T10 on Proxmox VE 9.2 with a Debian 13 guest; T11 on TrueNAS 25.10.7 (by whom).
Not run: T1–T9, T12, T13.

## Images
ghcr.io/mojokata/moolakata:0.2.0 and ghcr.io/mojokata/moolakata-connector:0.2.0, for amd64
and arm64, each with a build-provenance attestation:
gh attestation verify oci://ghcr.io/mojokata/moolakata:0.2.0 --owner MojoKata
```

- **What's new**: list the pull requests since the last tag with
  `git log --format='- %s' v0.1.0..upstream/main`. Each squash commit's subject ends in its
  number, and GitHub links `(#9)` to the pull request. Or use the release form's **Generate
  release notes** button, which does the same with authors. Add the base image's move from
  §3 step 3, naming the Debian packages it picked up.
- **Compatibility**: comes from the protocol changes found in §3 step 5.
- **Tried by hand**: the manual test plan requires every release to say which of T1–T13
  were run, by whom and on what, and which were not (S17.9.7.8). That includes T7, the arm64
  image on household hardware, which no runner replaces.
- Link to the documents at the tag (`https://github.com/MojoKata/MoolaKata/blob/v0.2.0/docs/DEPLOY.md`),
  so a later change on `main` doesn't move the instructions under an old release.

## 5. Publish the release

On GitHub, **Releases › Draft a new release**
(`https://github.com/MojoKata/MoolaKata/releases/new`):

1. **Tag**: type `v0.2.0` and choose **Create new tag: v0.2.0 on publish**. **Target**:
   `main`. If something merged after the release's pull request, pick that pull request's
   commit under **Recent commits** instead.
2. **Previous tag**: the last release (`v0.1.0`), which **Generate release notes** compares
   against.
3. **Release title**: `MoolaKata 0.2.0`. **Description**: the notes from §4.
4. **Set as a pre-release**: ticked while releases are for testers (0.1.0 was one).
5. **Publish release.** That makes the tag, and the tag starts the workflow. The release page
   is up about two minutes before its images are (§6).

Or from a terminal, with a GPG-signed tag in place of the one GitHub makes:

```sh
git fetch upstream
git tag -s v0.2.0 -m "MoolaKata 0.2.0" upstream/main     # the release's commit
git push upstream v0.2.0                                 # starts the workflow
gh release create v0.2.0 -R MojoKata/MoolaKata --verify-tag --prerelease \
  --title "MoolaKata 0.2.0" --notes-file notes.md
```

## 6. Watch the workflow

**Actions › release** shows the tag's run, or from a terminal:

```sh
gh run watch -R MojoKata/MoolaKata "$(gh run list -R MojoKata/MoolaKata --workflow release.yml \
  --branch v0.2.0 --limit 1 --json databaseId --jq '.[0].databaseId')"
```

Three jobs, about two minutes in all at 0.1.0:

1. **build and smoke (amd64)** and **build and smoke (arm64)**, side by side, on runners
   of their own architecture. Each first checks that the tag names `web/VERSION`, then runs
   `smoke.sh`, then pushes its images as `0.2.0-amd64` or `0.2.0-arm64`.
2. **one tag per image, attested**, once both have passed. It joins each image's two
   architectures under `0.2.0` and attests each joined image.

A failure says which step failed in the run's annotations (the job's page, or
`gh api repos/MojoKata/MoolaKata/check-runs/<job id>/annotations`). §9 says what to do next.

## 7. Check what was published

```sh
docker buildx imagetools inspect ghcr.io/mojokata/moolakata:0.2.0              # linux/amd64 and linux/arm64
docker buildx imagetools inspect ghcr.io/mojokata/moolakata-connector:0.2.0
gh attestation verify oci://ghcr.io/mojokata/moolakata:0.2.0 --owner MojoKata
gh attestation verify oci://ghcr.io/mojokata/moolakata-connector:0.2.0 --owner MojoKata
docker logout ghcr.io && docker pull ghcr.io/mojokata/moolakata:0.2.0          # pulls without signing in
```

Each `inspect` lists both platforms under one index. Each `verify` names the tag's run of
`release.yml` as the image's build. The anonymous pull proves the packages are still public.

## 8. Run DEPLOY.md with the release

The release isn't finished until its documented install has been run with the published
images:

1. **Upgrade a test server** on each host as `DEPLOY.md` §6 says, and **install one fresh**
   where the steps changed. Once it is unlocked, the app's sidebar shows the new version
   under the household's name, and the connector's page shows it beside its name:

   ![The version in MoolaKata's sidebar](release/version-app.png)

   ![The version on the connector's page](release/version-connector.png)

2. **Record the run** in a small pull request. `DEPLOY.md`'s second paragraph names this
   release and the versions of the hosts it was run on. Every other document already went
   with the release (§3 step 5), so the only other changes are fixes the run found. For
   0.1.0 this was the pull request *0.1.0 is published: DEPLOY.md run with the release
   itself*.
3. **Add the runs to the release's notes** (T10, T11 and any other test from the plan) with
   the release page's **Edit**.

## 9. When something goes wrong

- **The tag doesn't name the version** (*the tag names this version* fails): nothing was
  pushed. Delete the release and its tag, then publish again from §5 on the right commit:

  ```sh
  gh release delete v0.2.0 -R MojoKata/MoolaKata --cleanup-tag --yes
  ```

- **A build or smoke run fails.** No `0.2.0` tag exists on ghcr.io yet, only possibly the
  other architecture's `0.2.0-<arch>`. If the cause is outside the code (a runner, the
  network), use **Re-run failed jobs** on the run. If the code is at fault, delete the release
  and its tag as above, fix it in a pull request, and publish again with the same version.
  The next run overwrites the per-architecture tags.
- **The joining or attesting job fails**: **Re-run failed jobs**. It reads only the
  per-architecture images the builds pushed, so it can run again on its own.
- **Something is wrong after `0.2.0` was joined and published**: don't move the tag or the
  image. Fix forward with a new patch release (`0.2.1`) and say in `0.2.0`'s notes what is
  wrong with it.
