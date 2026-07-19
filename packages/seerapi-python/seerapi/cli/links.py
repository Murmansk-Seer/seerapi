import re


def parse_link_header(value: str) -> dict[str, str]:
    links: dict[str, str] = {}
    for part in value.split(','):
        part = part.strip()
        if not part:
            continue
        match = re.match(r'<([^>]+)>(.*)', part)
        if not match:
            continue
        url = match.group(1)
        for rel_match in re.finditer(r'rel="([^"]+)"', match.group(2)):
            links[rel_match.group(1)] = url
    return links


def get_link_rel(value: str, rel: str) -> str | None:
    return parse_link_header(value).get(rel)
