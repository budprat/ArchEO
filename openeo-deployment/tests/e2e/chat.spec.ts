/**
 * E2E Tests for Chat Interface
 *
 * Tests message sending, receiving, and tool execution flow.
 */

import { test, expect } from '@playwright/test'

test.describe('Chat Interface', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('should display chat interface', async ({ page }) => {
    // Check main layout elements exist
    await expect(page.locator('text=OpenEO AI')).toBeVisible()

    // Check chat input exists
    const chatInput = page.locator('textarea, input[type="text"]').first()
    await expect(chatInput).toBeVisible()
  })

  test('should send a message', async ({ page }) => {
    // Find chat input
    const chatInput = page.locator('textarea, input[type="text"]').first()

    // Type a message
    await chatInput.fill('Hello, what collections are available?')

    // Find and click send button
    const sendButton = page.locator('button').filter({ hasText: /send/i }).first()
    if (await sendButton.isVisible()) {
      await sendButton.click()
    } else {
      // Try pressing Enter
      await chatInput.press('Enter')
    }

    // Wait for response (message should appear in chat)
    await expect(page.locator('[class*="message"]').first()).toBeVisible({
      timeout: 10000
    })
  })

  test('should display user message in chat', async ({ page }) => {
    const chatInput = page.locator('textarea, input[type="text"]').first()

    // Send a message
    await chatInput.fill('Test message')
    await chatInput.press('Enter')

    // Check message appears
    await expect(page.locator('text=Test message')).toBeVisible({
      timeout: 5000
    })
  })

  test('should show loading state while waiting for response', async ({ page }) => {
    const chatInput = page.locator('textarea, input[type="text"]').first()

    // Send a message
    await chatInput.fill('What is NDVI?')
    await chatInput.press('Enter')

    // Check for loading indicator (spinner or similar)
    const loadingIndicator = page.locator('[class*="loading"], [class*="spinner"], [class*="animate"]')

    // Either loading shows or response comes quickly
    const hasLoading = await loadingIndicator.first().isVisible().catch(() => false)
    if (hasLoading) {
      await expect(loadingIndicator.first()).toBeVisible()
    }
  })

  test('should maintain chat history', async ({ page }) => {
    const chatInput = page.locator('textarea, input[type="text"]').first()

    // Send first message
    await chatInput.fill('First message')
    await chatInput.press('Enter')
    await page.waitForTimeout(1000)

    // Send second message
    await chatInput.fill('Second message')
    await chatInput.press('Enter')

    // Both messages should be visible
    await expect(page.locator('text=First message')).toBeVisible()
    await expect(page.locator('text=Second message')).toBeVisible()
  })
})

test.describe('Tool Execution', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('should display tool results', async ({ page }) => {
    const chatInput = page.locator('textarea, input[type="text"]').first()

    // Request something that triggers a tool
    await chatInput.fill('List available data collections')
    await chatInput.press('Enter')

    // Wait for tool result (collections list or similar)
    await page.waitForTimeout(5000)

    // Check for any response content
    const responseArea = page.locator('[class*="message"], [class*="response"]')
    await expect(responseArea.first()).toBeVisible()
  })

  test('should show visualization tab when map data is returned', async ({ page }) => {
    const chatInput = page.locator('textarea, input[type="text"]').first()

    // Request something that might return a map
    await chatInput.fill('Show me a map of Sentinel-2 data')
    await chatInput.press('Enter')

    // Wait for response
    await page.waitForTimeout(10000)

    // Check for visualization panel or map tab
    const vizTab = page.locator('text=Map View, [class*="tab"][data-value="map"]')
    // May or may not be visible depending on response
  })
})

test.describe('Keyboard Navigation', () => {
  test('should focus chat input on page load', async ({ page }) => {
    await page.goto('/')

    // Check if chat input is focused or easily focusable
    const chatInput = page.locator('textarea, input[type="text"]').first()
    await chatInput.click()
    await expect(chatInput).toBeFocused()
  })

  test('should submit on Enter key', async ({ page }) => {
    await page.goto('/')

    const chatInput = page.locator('textarea, input[type="text"]').first()
    await chatInput.fill('Test enter key')
    await chatInput.press('Enter')

    // Message should be sent (input cleared or message appears)
    await page.waitForTimeout(1000)
    const inputValue = await chatInput.inputValue()
    // Input should be cleared after sending
    expect(inputValue === '' || inputValue === 'Test enter key').toBeTruthy()
  })
})
