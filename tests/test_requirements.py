"""What the live app needs is installed: a missing package only fails on
Streamlit Community Cloud, at the moment someone clicks the button that
needs it."""


def test_sign_in_with_google_can_load():
    # What Streamlit imports when "Sign in with Google" is clicked; it needs
    # Authlib and httpx from requirements.txt.
    from authlib.integrations import starlette_client  # noqa: F401
    from streamlit.auth_util import is_authlib_installed

    assert is_authlib_installed()
