from types import SimpleNamespace

from capservice.storage import output_filename, parse_output_filename


def test_parses_uuid_output_names() -> None:
    job = SimpleNamespace(
        id="4d2c1a0e-8f1b-4c3a-9e2d-1a2b3c4d5e6f",
        output_token="abcTOKEN",
    )
    name = output_filename(job)
    parsed = parse_output_filename(name)
    assert parsed == (job.id, "abcTOKEN")


def test_rejects_path_traversal() -> None:
    assert parse_output_filename("../secret.mp4") is None
    assert parse_output_filename("not-a-uuid.mp4") is None
