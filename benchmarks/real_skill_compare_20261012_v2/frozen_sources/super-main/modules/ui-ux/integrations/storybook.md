# Storybook Integration & Component Contract

## Tool Contract

| Contract Element | Specification |
|---|---|
| **Pre-requisite** | Existing Storybook configuration in the project (`.storybook/` directory, `@storybook/react` or equivalent installed in `package.json`), or explicit user instruction to emit component stories. Storybook dev server or test runner must be functional. |
| **Input** | Target component path, component TypeScript interface/props contract, required state variations (Default, Hover, Active, Disabled, Loading, Error, Content-Extremes), mock theme decorators, and responsive viewport parameters. |
| **Expected Outcome** | Component Story Format (CSF 3.0) file (`[ComponentName].stories.tsx`) rendering all defined states with full keyboard navigability and passing `@storybook/addon-a11y` tests with 0 accessibility violations. |
| **Failure Condition** | Missing component exports, runtime JSX/TSX compilation errors, unhandled prop variants causing canvas crashes, missing accessibility labels, or failing `@storybook/addon-a11y` automated checks. |

---

## 1. Operational Guidelines

Use Storybook when the project already uses it or a reusable component library is part of the request. Add stories for the component states and content extremes that matter to the workflow. Use the official accessibility testing integration when available, and inspect reported violations in context.

Automated accessibility results do not cover every WCAG criterion. Check focus order, wording, and representative screen behavior manually. For a one-off page, avoid introducing Storybook solely to satisfy a process step.

---

## 2. CSF 3.0 Story Pattern

```tsx
import type { Meta, StoryObj } from '@storybook/react';
import { Button } from './Button';

const meta: Meta<typeof Button> = {
  title: 'Components/Button',
  component: Button,
  parameters: {
    a11y: {
      config: {
        rules: [{ id: 'color-contrast', enabled: true }],
      },
    },
  },
  argTypes: {
    variant: {
      control: 'select',
      options: ['default', 'secondary', 'destructive', 'outline', 'ghost', 'link'],
    },
    size: {
      control: 'select',
      options: ['default', 'sm', 'lg', 'icon'],
    },
  },
};

export default meta;
type Story = StoryObj<typeof Button>;

export const Default: Story = {
  args: {
    children: 'Action Button',
    variant: 'default',
  },
};

export const Disabled: Story = {
  args: {
    children: 'Disabled State',
    disabled: true,
  },
};
```
