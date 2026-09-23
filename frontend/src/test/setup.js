/**
 * Test setup, run once before every test file.
 *
 * Part of: frontend / tests.
 *
 * Adds the readable matchers (toBeInTheDocument and friends) and clears mocks
 * between tests, so one test's stubbed API response can never leak into the
 * next and make a failure look like a pass.
 */

import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})
