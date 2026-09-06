import { createContext, useContext } from 'react'

/** Presentation only. Mobile and standalone component consumers retain their UI. */
export const EmberPresentation = createContext(false)
export const useEmberDesktop = () => useContext(EmberPresentation)
