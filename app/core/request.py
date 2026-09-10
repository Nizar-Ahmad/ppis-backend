from fastapi import Request


def get_request_ip(
    request: Request,
) -> str | None:
    cf_ip = request.headers.get(
        "cf-connecting-ip"
    )

    if cf_ip:
        return cf_ip.strip()[:45]

    forwarded = request.headers.get(
        "x-forwarded-for"
    )

    if forwarded:
        return (
            forwarded
            .split(",")[0]
            .strip()[:45]
        )

    if request.client:
        return request.client.host[:45]

    return None


def get_user_agent(
    request: Request,
) -> str | None:
    value = request.headers.get(
        "user-agent"
    )

    if not value:
        return None

    return value[:1000]