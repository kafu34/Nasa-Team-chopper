import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { BodyMap } from './BodyMap'

describe('BodyMap', () => {
  it('preserves region and laterality for keyboard selection', () => {
    const onChange = vi.fn()
    render(<BodyMap value={null} onChange={onChange} />)
    fireEvent.keyDown(screen.getByRole('button', { name: 'Left chest' }), { key: 'Enter' })
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ regionId: 'chest', laterality: 'left' }))
    fireEvent.click(screen.getByRole('button', { name: 'Back' }))
    fireEvent.click(screen.getByRole('button', { name: 'Right upper back' }))
    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({ regionId: 'upper_back', laterality: 'right' }))
  })
})
