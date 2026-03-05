import * as React from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';
import { Loader2 } from 'lucide-react';

import { cn } from '@/lib/utils';

const buttonVariants = cva(
  'inline-flex items-center justify-center whitespace-nowrap rounded-md font-light text-sm transition-all duration-300 ease-in-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-purple-600 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0',
  {
    variants: {
      variant: {
        primary:
          'bg-purple-600 text-white shadow-sm hover:bg-purple-700 hover:shadow-md active:scale-95',
        secondary:
          'border border-silver-400 bg-transparent text-purple-600 hover:bg-purple-50 hover:border-purple-300',
        ghost:
          'text-purple-600 hover:bg-purple-50 hover:text-purple-700',
        destructive:
          'bg-red-600 text-white shadow-sm hover:bg-red-700 hover:shadow-md',
        outline:
          'border border-purple-200 bg-transparent text-purple-600 hover:bg-purple-50 hover:border-purple-400',
        link:
          'text-purple-600 underline-offset-4 hover:underline hover:text-purple-700',
      },
      size: {
        sm: 'h-8 rounded-md px-3 text-xs',
        md: 'h-10 px-4 py-2',
        lg: 'h-12 rounded-md px-8 text-base',
        icon: 'h-10 w-10',
      },
    },
    defaultVariants: {
      variant: 'primary',
      size: 'md',
    },
  }
);

export interface NeuralPurpleButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
  loading?: boolean;
  loadingText?: string;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

const NeuralPurpleButton = React.forwardRef<HTMLButtonElement, NeuralPurpleButtonProps>(
  (
    {
      className,
      variant,
      size,
      asChild = false,
      loading = false,
      loadingText,
      leftIcon,
      rightIcon,
      children,
      disabled,
      ...props
    },
    ref
  ) => {
    const Comp = asChild ? Slot : 'button';
    const isDisabled = disabled || loading;

    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        disabled={isDisabled}
        aria-busy={loading}
        aria-disabled={isDisabled}
        {...props}
      >
        {loading ? (
          <>
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            {loadingText || children}
          </>
        ) : (
          <>
            {leftIcon && <span className="mr-2">{leftIcon}</span>}
            {children}
            {rightIcon && <span className="ml-2">{rightIcon}</span>}
          </>
        )}
      </Comp>
    );
  }
);

NeuralPurpleButton.displayName = 'NeuralPurpleButton';

// Button Group Component
interface ButtonGroupProps {
  children: React.ReactNode;
  className?: string;
  orientation?: 'horizontal' | 'vertical';
}

export const ButtonGroup: React.FC<ButtonGroupProps> = ({
  children,
  className,
  orientation = 'horizontal',
}) => {
  return (
    <div
      className={cn(
        'flex',
        orientation === 'vertical' ? 'flex-col' : 'flex-row',
        '[&>*:not(:first-child)]:rounded-l-none [&>*:not(:last-child)]:rounded-r-none',
        orientation === 'vertical' && '[&>*:not(:first-child)]:rounded-t-none [&>*:not(:last-child)]:rounded-b-none',
        '[&>*:not(:last-child)]:border-r-0',
        orientation === 'vertical' && '[&>*:not(:last-child)]:border-b-0 [&>*:not(:last-child)]:border-r',
        className
      )}
      role="group"
    >
      {children}
    </div>
  );
};

// Icon Button Component
interface IconButtonProps extends NeuralPurpleButtonProps {
  'aria-label': string;
}

export const IconButton = React.forwardRef<HTMLButtonElement, IconButtonProps>(
  ({ size = 'icon', ...props }, ref) => {
    return <NeuralPurpleButton ref={ref} size={size} {...props} />;
  }
);

IconButton.displayName = 'IconButton';

// Toggle Button Component
interface ToggleButtonProps extends Omit<NeuralPurpleButtonProps, 'variant'> {
  pressed?: boolean;
  onPressedChange?: (pressed: boolean) => void;
}

export const ToggleButton = React.forwardRef<HTMLButtonElement, ToggleButtonProps>(
  ({ pressed = false, onPressedChange, className, ...props }, ref) => {
    const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
      onPressedChange?.(!pressed);
      props.onClick?.(e);
    };

    return (
      <NeuralPurpleButton
        ref={ref}
        variant={pressed ? 'primary' : 'outline'}
        aria-pressed={pressed}
        onClick={handleClick}
        className={cn(
          pressed && 'bg-purple-600 text-white hover:bg-purple-700',
          className
        )}
        {...props}
      />
    );
  }
);

ToggleButton.displayName = 'ToggleButton';

export { NeuralPurpleButton, buttonVariants };