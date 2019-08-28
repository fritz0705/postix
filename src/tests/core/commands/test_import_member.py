import tempfile

import pytest
from django.core.management import call_command

from postix.core.models import ListConstraint


@pytest.yield_fixture
def sample_member_file_ccc():
    with tempfile.NamedTemporaryFile() as t:
        t.write(
            b"""chaos_number	first_name	last_name	state
2			bezahlt
4	A	B	Verzug

5	C	D	bezahlt
8	E	F	bezahlt
11	G	H	ruhend
14	I	J	ruhend
23	K	L	bezahlt
"""
        )
        t.seek(0)
        yield t.name


@pytest.yield_fixture
def sample_member_file_incremental_update_ccc():
    with tempfile.NamedTemporaryFile() as t:
        t.write(
            b"""chaos_number	first_name	last_name	state
2			bezahlt
4	A	B	Verzug
8	E	Y	bezahlt
11	G	H	ruhend
14	I	J	ruhend
23	K	L	ruhend
42	M	N	bezahlt
43      O       P       Verzug
"""
        )
        t.seek(0)
        yield t.name


@pytest.mark.django_db
def test_member_import_ccc(sample_member_file_ccc):
    call_command("import_member", sample_member_file_ccc)
    lc = ListConstraint.objects.get(confidential=True, name="Mitglieder")
    assert set((e.identifier, e.name) for e in lc.entries.all()) == {
        ("2", " "),
        ("5", "C D"),
        ("8", "E F"),
        ("23", "K L"),
    }


@pytest.mark.django_db
def test_member_import_ccc_update(
    sample_member_file_ccc, sample_member_file_incremental_update_ccc
):
    call_command("import_member", sample_member_file_ccc)
    lc = ListConstraint.objects.get(confidential=True, name="Mitglieder")
    call_command("import_member", sample_member_file_incremental_update_ccc)
    assert set((e.identifier, e.name) for e in lc.entries.all()) == {
        ("2", " "),
        (
            "5",
            "C D",
        ),  # got removed from the file, but we don't detect that so we can apply partial lists as well
        ("8", "E Y"),  # name changed :)
        ("42", "M N"),
    }


@pytest.yield_fixture
def sample_member_file_local():
    with tempfile.NamedTemporaryFile() as t:
        t.write(
            b"""CHAOSNR;NAME
1;foo
2;bar
"""
        )
        t.seek(0)
        yield t.name


@pytest.mark.django_db
def test_member_import_local(sample_member_file_local):
    call_command("import_member", sample_member_file_local, prefix="BLN")
    lc = ListConstraint.objects.get(confidential=True, name="Mitglieder")
    assert set((e.identifier, e.name) for e in lc.entries.all()) == {
        ("BLN-1", "foo"),
        ("BLN-2", "bar"),
    }
