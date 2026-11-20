# UAC transaction semantics

`app.preferences.uac.transaction()` stages User Access Control operations locally before
`commit()` sends them.

```python
with app.preferences.uac.transaction() as transaction:
    transaction.create_user(
        "E2E-demo-user",
        password="test-password",
        full_name="Demo User",
    )
    transaction.update_role("role-id", description="Updated description")
    transaction.update_permission_template("template-id", description="Updated description")

    result = transaction.commit()
    if not result.ok:
        for failure in result.failed:
            print(failure.kind, failure.entity_id, failure.message)
```

## Users are not atomic

`userman/addUser`, `userman/updateUser`, and `userman/deleteUser` accept one object in
`data`; a captured array request was rejected with `INVALID_REQUEST`. A UAC transaction
therefore sends user operations sequentially:

- Every operation performs an Inspect-style baseline re-fetch and field comparison.
- The fresh `_rev` is used for the final user action.
- A failed user operation is recorded and later user operations are still attempted.
- There is no rollback across user operations.

This is a **client-side unit of work**, not a database or server transaction. `UacCommitResult`
must be inspected because `commit()` can return a partial result.

## Domains, roles, and permission templates use PATCH batches

Domains, roles, and permission templates use VideoIPath's REST PATCH `actions` format.
Staged operations are grouped into one strict request per collection:

- domains: `/rest/v2/data/config/domainman/domains`
- roles: `/rest/v2/data/config/security/users/roles`
- permission templates: `/rest/v2/data/config/security/users/permissionTemplates`

Within each request, operations are sent together. Any server-level request failure marks the
operations in that collection as failed. A conflict detected during preflight removes only that
operation from the batch, and the remaining actions are still sent.

The captures verify multi-action request shape but not every server-version rollback guarantee.


## Convenience methods

Direct methods such as `create_user()` and `update_role()` remain available. They stage one
operation, commit immediately, return the refreshed domain object, and raise the recorded error
when the single operation fails.

Use the explicit transaction form when staging multiple changes or when partial failure
reporting is required.
