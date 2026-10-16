# External sources

Copies of the outside documents the requirements rest on, kept here in case their links break.
Each entry names where it came from, the revision or date it was taken, its licence, and the
requirements that cite it.

| File | Source | Taken | Licence | Cited by |
|---|---|---|---|---|
| `schwab-py-auth.rst` | [schwab-py, `docs/auth.rst`](https://github.com/alexgolec/schwab-py/blob/43c4614965bdc434bd87fcd49f959db66338185e/docs/auth.rst) (rendered at [schwab-py.readthedocs.io](https://schwab-py.readthedocs.io/en/latest/auth.html)) | commit `43c4614`, 2026-10-16 | MIT (`schwab-py-LICENSE`) | S18.9.2: the access token lasts about 30 minutes and the refresh token about seven days; the authorization code's lifetime is not published |
| `schwab-py-LICENSE` | [schwab-py, `LICENSE`](https://github.com/alexgolec/schwab-py/blob/43c4614965bdc434bd87fcd49f959db66338185e/LICENSE) | commit `43c4614`, 2026-10-16 | MIT | the licence of the file above |
| `irs-f8949-2025.pdf` | [Form 8949 (2025)](https://www.irs.gov/pub/irs-pdf/f8949.pdf), IRS | 2026-10-16 | US government work, public domain | S8.1: boxes A to L |
| `irs-i8949-2025.pdf` | [Instructions for Form 8949 (2025)](https://www.irs.gov/pub/irs-pdf/i8949.pdf), IRS | 2026-10-16 | US government work, public domain | S8.1: boxes G to L for digital assets; C and F not for them |

SHA-256:

```
ef2e6abfe9fe83076a1a36d5e3118a933bf08d05a7fe2d959f3f5ca202a3253c  schwab-py-auth.rst
ef4b67c406ef65c55b6fb21252e39c6088d83e37be87fa3cbd2d0bbb61ce418f  schwab-py-LICENSE
274513891e4e281d11e14286f14b9df724c24b6030fca0f0681da64fb2e7f525  irs-f8949-2025.pdf
f077991c83b086810c46cbad3755e0f126cb8dfd88cf8bf8ab2d5605d6e7ab45  irs-i8949-2025.pdf
```

The IRS publishes each year's form and instructions at the same address, so a copy is named by
its tax year, and a new year's is added beside it rather than over it.

Pages from commercial sites (accountants' guides) are cited by link only, never copied: the
IRS's own instructions are the source of record.
