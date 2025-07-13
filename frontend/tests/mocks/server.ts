import { setupServer } from 'msw/node'
import { handlers } from './api-handlers'

// Setup requests interception using the given handlers
export const server = setupServer(...handlers)

// Helper to reset handlers for specific tests
export const resetHandlers = () => {
  server.resetHandlers(...handlers)
}

// Helper to add additional handlers for specific tests
export const addHandlers = (...newHandlers: any[]) => {
  server.use(...newHandlers)
}