"""Self-custody wallets (requirements S1.6.1, S1.6.3): extended public keys and addresses, the
addresses derived from a key, and keys and seed phrases refused."""

import logging

import pytest
from conftest import make_user, sign_in
from test_accounts import new_account

from moneykata.bitcoin import keys

# The BIP84, BIP49 and BIP44 test wallets ("abandon abandon … about"), whose addresses are
# published with those standards.
ZPUB = (
    "zpub6rFR7y4Q2AijBEqTUquhVz398htDFrtymD9xYYfG1m4wAcvPhXNfE3EfH1r1ADqtfSdVCToUG868Rv"
    "UUkgDKf31mGDtKsAYz2oz2AGutZYs"
)
YPUB = (
    "ypub6Ww3ibxVfGzLrAH1PNcjyAWenMTbbAosGNB6VvmSEgytSER9azLDWCxoJwW7Ke7icmizBMXrzBx9979Ff"
    "aHxHcrArf3zbeJJJUZPf663zsP"
)
XPUB = (
    "xpub6BosfCnifzxcFwrSzQiqu2DBVTshkCXacvNsWGYJVVhhawA7d4R5WSWGFNbi8Aw6ZRc1brxMyWMzG3DSSS"
    "SoekkudhUd9yLb6qx39T9nMdj"
)
SEED = "abandon " * 11 + "about"
WIF = "5HueCGU8rMjxEXxiPuD5BDku4MkFqeZyd4dZ1jvhTVqvbTLvyTJ"
HEX = "0c28fca386c7a227600b2fe50b7cae11ec86d3bf1fbe471be89827e19d72aa1d"
XPRV = (
    "xprv9s21ZrQH143K3QTDL4LXw2F7HEK3wJUD2nW2nRk4stbPy6cq3jPPqjiChkVvvNKmPGJxWUtg6LnF5kejMR"
    "NNU3TGtRBeJgk33yuGBxrMPHi"
)


def test_keys_derive_the_published_addresses():
    z = keys.extended(ZPUB)
    assert z.address(0, 0) == "bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu"
    assert z.address(0, 1) == "bc1qnjg0jd8228aq7egyzacy8cys3knf9xvrerkf9g"
    assert z.address(1, 0) == "bc1q8c6fshw2dlwun7ekn9qwf37cu2rn755upcp6el"
    assert keys.extended(YPUB).address(0, 0) == "37VucYSaXLCAsxYyAPfbSi9eh4iEcbShgf"
    assert keys.extended(XPUB).address(0, 0) == "1LqBGSKuX5yYUonjxT5qGfpUsXKYYWeabA"


def test_addresses_are_checked():
    assert keys.address_script("bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu") == "p2wpkh"
    assert keys.address_script("3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy") == "p2sh"
    assert keys.address_script("1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2") == "p2pkh"
    tr = "bc1p5d7rjq7g6rdk2yhzks9smlaqtedr4dekq08ge8ztwac72sfr9rusxg3297"
    assert keys.address_script(tr) == "p2tr"
    for bad, code in (
        ("1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN3", "address-invalid"),  # checksum
        ("tb1qw508d6qejxtdg4y5r3zarvary0c5xw7kxpjzsx", "testnet"),
        ("hello", "address-invalid"),
    ):
        with pytest.raises(keys.Refused) as e:
            keys.address_script(bad)
        assert e.value.code == code


@pytest.mark.parametrize(
    "text,what",
    [
        (SEED, "seed phrase"),
        (SEED.upper(), "seed phrase"),
        (" ".join(["zoo"] * 23 + ["wrong"]), "seed phrase"),
        (WIF, "private key (WIF)"),
        ("KwdMAjGmerYanjeui5SHS7JkmpZvVipYvB2LJGU1ZxJwYvP98617", "private key (WIF)"),
        (HEX, "private key (64 hex digits)"),
        (XPRV, "extended private key"),
        (ZPUB + "\n" + WIF, "private key (WIF)"),
    ],
)
def test_secrets_are_recognised(text, what):
    assert keys.secret_kind(text) == what


def test_public_data_is_not_mistaken_for_a_secret():
    assert keys.secret_kind(ZPUB) is None
    assert (
        keys.secret_kind(
            "bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu 37VucYSaXLCAsxYyAPfbSi9eh4iEcbShgf"
        )
        is None
    )


@pytest.fixture
def alice(server):
    make_user(server, "alice")
    return sign_in(server, "alice")


def test_a_wallet_watches_a_keys_addresses_up_to_the_gap_limit(alice):
    w = new_account(alice, name="Cold storage", type="crypto-wallet")
    r = alice.put(f"/ui/api/accounts/{w['id']}/wallet", json={"text": ZPUB})
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["keys"][0]["script"] == "p2wpkh" and v["keys"][0]["gapLimit"] == 20
    assert v["watched"] == 40, "20 receive and 20 change"
    first = v["addresses"][0]
    assert (first["address"], first["chain"], first["index"]) == (
        "bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu",
        0,
        0,
    )
    assert len(v["addresses"]) == 20, "the first 10 a chain are shown"
    # An address added, the gap limit narrowed: the key keeps its addresses.
    r = alice.put(
        f"/ui/api/accounts/{w['id']}/wallet",
        json={"text": ZPUB + "\n3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy", "gapLimit": 5},
    )
    v = r.json()
    assert [k["kind"] for k in v["keys"]] == ["xpub", "address"]
    assert v["keys"][0]["gapLimit"] == 5 and v["watched"] == 41
    # The key taken out: its addresses go with it.
    v = alice.put(
        f"/ui/api/accounts/{w['id']}/wallet", json={"text": "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy"}
    ).json()
    assert v["watched"] == 1 and v["addresses"][0]["chain"] is None
    assert alice.get(f"/ui/api/accounts/{w['id']}/wallet").json()["watched"] == 1


def test_a_seed_phrase_or_private_key_is_refused_and_never_repeated(alice, caplog):
    w = new_account(alice, name="Cold storage", type="crypto-wallet")
    caplog.set_level(logging.DEBUG)
    for text in (SEED, WIF, HEX, XPRV):
        r = alice.put(f"/ui/api/accounts/{w['id']}/wallet", json={"text": text})
        assert r.status_code == 422
        assert r.json()["code"] == "secret-refused"
        assert r.json()["errors"][0]["field"] == "text"
        assert text.split()[0] not in r.text
    assert not any(SEED.split()[1] in m or WIF in m or HEX in m for m in caplog.messages)
    assert alice.get(f"/ui/api/accounts/{w['id']}/wallet").json()["watched"] == 0


def test_only_a_wallet_holds_keys(alice):
    b = new_account(alice, name="Brokerage", type="brokerage")
    r = alice.put(f"/ui/api/accounts/{b['id']}/wallet", json={"text": ZPUB})
    assert r.status_code == 422 and r.json()["code"] == "not-a-wallet"
    w = new_account(alice, name="Cold storage", type="crypto-wallet")
    r = alice.put(f"/ui/api/accounts/{w['id']}/wallet", json={"text": ZPUB[:-1] + "a"})
    assert r.json()["code"] == "key-invalid"
