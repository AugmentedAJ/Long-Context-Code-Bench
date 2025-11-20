import { test, expect } from '@playwright/test';

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:3000';

test.describe('Head-to-head web UI', () => {
  test('PR detail view shows pairwise decisions with rationale', async ({ page }) => {
    // Navigate to the main dashboard.
    await page.goto(`${BASE_URL}/`);

    // Wait for the head-to-head PR list to populate.
    await page.waitForSelector('#h2h-pr-list-body tr');

	    // The PR list table should include a Winner column.
	    const prListHeaderCells = page.locator('#analysis-list thead tr th');
	    await expect(prListHeaderCells.nth(3)).toHaveText(/Winner/i);

    const firstRow = page.locator('#h2h-pr-list-body tr').first();
    const prNumberText = (await firstRow.locator('td').first().innerText()).trim();

	    // Winner cell in the list should not be empty.
	    const listWinnerCell = firstRow.locator('td').nth(3);
	    await expect(listWinnerCell).not.toHaveText(/^\s*$/);

    // Click "View Details" for the first PR.
    await firstRow.getByRole('button', { name: /view details/i }).click();

    // The detail title should include the PR number.
    await expect(page.locator('#detail-title')).toContainText(prNumberText);

    // Agent results header should reflect head-to-head metrics (no legacy scalar columns).
    const agentHeaderCells = page.locator('#agent-results-table thead tr th');
    await expect(agentHeaderCells.nth(3)).toHaveText(/Matches/i);
    await expect(agentHeaderCells).not.toContainText(/Code Reuse/i);

    // Pairwise decisions card should render with at least one row.
    const pairwiseContent = page.locator('#pairwise-decisions-content');
    await expect(pairwiseContent).toBeVisible();

    const firstDecisionRow = pairwiseContent.locator('#pairwise-tbody tr').first();
    await expect(firstDecisionRow).toBeVisible();

    // Winner cell should not be empty.
    const winnerCell = firstDecisionRow.locator('td').nth(3);
    await expect(winnerCell).not.toHaveText(/^\s*$/);

    // Rationale / notes cell should contain some text.
    const rationaleCell = firstDecisionRow.locator('td').nth(5);
    await expect(rationaleCell).not.toHaveText(/^\s*$/);

	    // Side-by-side inspector should be visible with left/right selectors.
	    const comparisonCard = page.locator('#agent-comparison-card');
	    await expect(comparisonCard).toBeVisible();

	    const leftSelect = page.getByLabel(/Left side/i);
	    const rightSelect = page.getByLabel(/Right side/i);
	    await expect(leftSelect).toBeVisible();
	    await expect(rightSelect).toBeVisible();

	    // Each side should offer a Human option.
	    await expect(leftSelect).toContainText(/Human \(ground truth\)/i);

	    // Default right-side content should not be empty.
	    const rightContent = page.locator('#comparison-right-content');
	    await expect(rightContent).not.toHaveText(/^\s*$/);

	    // Switch right side to human + summary view and verify description text.
	    await rightSelect.selectOption({ label: /Human \(ground truth\)/i });
	    const rightSummaryButton = page.locator('#comparison-right-view-toggle').getByRole('button', { name: /Summary/i });
	    await rightSummaryButton.click();
	    await expect(rightContent).toContainText(/Human ground truth/i);
  });
});
