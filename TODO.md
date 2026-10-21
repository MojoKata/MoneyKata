# TODO: before PR #10 merges

PR #10 (`release-docs`) adds `docs/RELEASE.md`: signed tags, immutable releases, a release
drafted by `release.yml` with the tag's install files, and the images copied to Docker Hub.
A maintainer has to do items 1–4 below before it merges. RELEASE.md §1 has the details and
links. This file is only for working through that list. It is removed before the merge (see
the handoff at the end).

## Your part

1. [ ] **Attach 0.1.0's install files to its release.** DEPLOY.md now links to them. From a
   clone with the `v0.1.0` tag, signed in to `gh`:

   ```sh
   dir=$(mktemp -d)
   git archive v0.1.0 web/install | tar -x -C "$dir"
   gh release upload v0.1.0 -R MojoKata/MoolaKata "$dir"/web/install/compose*.yaml \
     "$dir"/web/install/moolakata.toml "$dir"/web/install/proxy/*
   ```

2. [ ] **Two settings in MojoKata/MoolaKata:**
   1. [ ] **Settings**, scroll to **Releases**, then tick **Enable release immutability**.
   2. [ ] **Settings › Rules › Rulesets › New ruleset › New tag ruleset**:
      - target tags matching `v*`;
      - turn on **Restrict creations**, **Restrict updates** and **Restrict deletions**;
      - put yourself (or the admin role) in the bypass list.
3. [ ] **Docker Hub:**
   1. [ ] Sign up at [hub.docker.com](https://hub.docker.com/signup) with the Docker ID
      **`mojokata`**. Turn on two-factor authentication, and save the password and recovery
      codes in the password manager.
   2. [ ] Create two **Public** repositories, `moolakata` and `moolakata-connector`. Each
      description links to https://github.com/MojoKata/MoolaKata and `docs/DEPLOY.md`, and
      shows the pull command with its tag: `docker pull mojokata/moolakata:0.1.0`.
   3. [ ] In [Docker Home](https://app.docker.com/), go to your avatar › **Account settings ›
      Personal access tokens › Generate new token**:
      - description *MoolaKata releases*;
      - **Repo Read & Write**;
      - an expiry date within a year, with a calendar reminder to renew it before then.
   4. [ ] In MojoKata/MoolaKata, go to **Settings › Environments › New environment** and create
      `docker-hub`:
      - under **Deployment branches and tags**, choose **Selected branches and tags** and add
        the tag rule `v*`;
      - add the secret `DOCKERHUB_TOKEN` (the token);
      - add the variable `DOCKERHUB_USERNAME` = `mojokata`.
   5. [ ] Apply to the
      [Docker-Sponsored Open Source program](https://www.docker.com/community/open-source/application/).
      It lifts the pull limit, and must be renewed every year.
   6. [ ] Copy 0.1.0 there once:

      ```sh
      docker login docker.io -u mojokata
      for image in moolakata moolakata-connector; do
        docker buildx imagetools create -t docker.io/mojokata/$image:0.1.0 ghcr.io/mojokata/$image:0.1.0
      done
      ```

4. [ ] **Delete 0.1.0's attestation tags on ghcr.io.** Do this on each package's page,
   [`moolakata`](https://github.com/orgs/MojoKata/packages/container/package/moolakata) and
   [`moolakata-connector`](https://github.com/orgs/MojoKata/packages/container/package/moolakata-connector):
   1. Go to **View and manage all versions**.
   2. Open the **⋯** beside the **`sha256-…`** version only. Leave `0.1.0`, `0.1.0-amd64` and
      `0.1.0-arm64` alone.
   3. Choose **Delete version**.

   The attestations stay in GitHub's store, so `gh attestation verify` still passes.
5. [ ] **Give Claude final approval of the Q27 and Q28 decisions** (summarised in the handoff
   below), or say what to change.
6. [ ] **Tell Claude your part is done.** Claude then works through the handoff below.
7. [ ] **Review and merge PR #10** once Claude has removed this file and `check` is green:
   https://github.com/MojoKata/MoolaKata/pull/10

## Handoff: where Claude picks up

**State when this file was written.** Branch `release-docs` on the fork
(`donclaudio777/MoolaKata`), PR #10 into `MojoKata/MoolaKata` `main`. Every decision below is
already written into the branch: `docs/RELEASE.md`, `.github/workflows/release.yml`,
S17.8.2 and S17.10.2–3, `docs/DEPLOY.md`, `docs/operations.md` and the README. On the PR,
`release.yml`'s build and smoke runs passed on both architectures, and `check` was running.

**Decisions made in review (each was locked one at a time):**

1. **Q26, versions:** semver. A major release is an upgrade that needs something from people
   beyond the new tag and an unlock, and its notes open with **Before you upgrade**. A minor
   release is features and a patch is fixes. A silent migration can come in any of them.
   There's no 0.x exception.
2. **Q27.1, the tag:** the maintainer signs it by hand with GPG and pushes it. The `v*` tag
   ruleset protects it.
3. **Q27.2, immutable releases:** on. The release is published only after `release.yml` and
   the §7 checks.
4. **Q27.3, the images' signatures:** Sigstore provenance attestations, checked strictly
   (`-R MojoKata/MoolaKata --signer-workflow …/release.yml --source-ref refs/tags/v<version>
   --deny-self-hosted-runners`). No cosign, no Content Trust, no SBOM.
5. **Q27.4, release files:** `release.yml`'s `draft` job, the only one with
   `contents: write`, drafts the release with the tag's eight install files. The maintainer
   publishes it with `gh release edit --draft=false`.
6. **Q28.1–Q28.2, Docker Hub:** publish there too. A free account `mojokata`, with a personal
   access token (Repo Read & Write) kept in the `docker-hub` environment, which only `v*` tags
   can read.
7. **Q28.3, the copy:** `release.yml`'s `docker-hub` job copies the joined images with
   `docker buildx imagetools create` and checks that the digests are unchanged. With Docker
   Hub not set up, it only warns.
8. **Q28.4, the primary registry:** ghcr.io stays the one the compose files and docs name.
   Docker Hub is the named alternative.
9. **Q28.5, tags:** exact versions only, with no `latest`.
10. **Q29, where attestations are kept:** `push-to-registry: false`, so they live in GitHub's
    attestation store and not as `sha256-…` tags on ghcr.io.

**What Claude checks once your part is done, then reports:**

1. **0.1.0's files:** `gh release view v0.1.0 -R MojoKata/MoolaKata --json assets --jq '.assets[].name'`
   lists the eight files, and
   `curl -fsSLI https://github.com/MojoKata/MoolaKata/releases/download/v0.1.0/compose.tls.yaml`
   answers.
2. **RELEASE.md §8's screenshot:** retake it from
   https://github.com/MojoKata/MoolaKata/releases/tag/v0.1.0 with **Assets** open, in headless
   Chromium at 1280 wide. Crop it to the release card, save it as a 256-colour PNG to
   `docs/release/release-page.png`, and look at it before committing.
3. **The ruleset:** `gh api repos/MojoKata/MoolaKata/rulesets` shows a tag ruleset on `v*`.
   If the immutability setting can't be read without admin access, ask.
4. **The environment:** `gh api repos/MojoKata/MoolaKata/environments --jq '.environments[].name'`
   includes `docker-hub`, and its deployment policies allow only `v*` tags.
5. **Docker Hub:** `curl -s https://hub.docker.com/v2/repositories/mojokata/` lists both
   repositories. On `docker.io/mojokata/<image>:0.1.0`, `docker buildx imagetools inspect`
   shows the same digests as ghcr.io (`sha256:b15777a3…` for the server,
   `sha256:8aab8776…` for the connector). The strict `gh attestation verify` passes on both
   copies.
6. **ghcr.io's tags:** each package's tag list
   (`https://ghcr.io/v2/mojokata/<image>/tags/list`, with an anonymous pull token) no longer
   has a `sha256-…` tag.
7. **Remove this file** and commit, quick checks only. Push, and wait for PR #10's `check`.
   Then tell the user it's ready to merge.
8. **After the merge:** the next release follows `docs/RELEASE.md`. It is the first real run
   of the `docker-hub` and `draft` jobs, so watch them, and read any failure from the run's
   annotations.

**Working notes for this machine:**

1. Push and fetch with `git -c protocol.version=0`, with
   `GIT_SSH_COMMAND="ssh -i ~/.ssh/id_ed25519_personal -o BatchMode=yes"`.
2. `docs.github.com` and `docs.docker.com` are blocked here. Check links against their
   sources in `github/docs` and `docker/docs` on raw.githubusercontent.com.
3. github.com's pages render styled in headless Chromium, now that `github.githubassets.com`
   and `avatars.githubusercontent.com` are open.
