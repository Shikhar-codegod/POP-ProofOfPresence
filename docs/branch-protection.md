# Branch Protection for `main`

Open the repository on GitHub:

1. Select **Settings**.
2. Select **Branches** under **Code and automation**.
3. Under **Branch protection rules**, select **Add branch protection rule**.
4. Set **Branch name pattern** to `main`.
5. Enable **Require a pull request before merging**.
6. Enable **Require approvals** and set the required approval count appropriate for the repository.
7. Enable **Require status checks to pass before merging**.
8. Search for and select the `POP CI / lint-and-test` status check.
   - The exact status name depends on GitHub Actions after the workflow has run once.
   - If it is not selectable yet, open one pull request or push a branch to make the workflow run.
9. Enable **Require branches to be up to date before merging** when available.
10. Enable **Do not allow bypassing the above settings** for administrator protection if it is consistent with repository policy.
11. Under **General** branch settings, enable **Automatically delete head branches**.
12. Save the branch protection rule.

## Validation

Create a non-main branch and pull request. Confirm that merging is blocked until the required `lint-and-test` job passes and the configured approvals are present.
