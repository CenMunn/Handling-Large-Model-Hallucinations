"""Validate supported gateway request shapes without adopting client rules.

The optional client system message is ignored.  The gateway must set its own
task instructions and must not log raw message content as part of the shape.
"""

def parse_messages(messages):
    """Return the unchanged user text and a content-free input-shape label.

    Accepted shapes: [user] or [system, user], where both message contents are
    nonempty text and each message has only the role and content fields.
    """
    if not isinstance(messages, list) or len(messages) not in (1, 2):
        raise ValueError('unsupported message sequence')
    for message in messages:
        if not isinstance(message, dict) or set(message) != {'role', 'content'}:
            raise ValueError('invalid message object')
        if not isinstance(message['role'], str) or not isinstance(message['content'], str):
            raise ValueError('message role and content must be text')
        if not message['content'].strip():
            raise ValueError('message text must not be empty')
    roles = [message['role'] for message in messages]
    if roles == ['user']:
        return {'question': messages[0]['content'], 'input_shape': 'user_only'}
    if roles == ['system', 'user']:
        return {'question': messages[1]['content'], 'input_shape': 'legacy_system_user'}
    raise ValueError('unsupported message roles or order')
