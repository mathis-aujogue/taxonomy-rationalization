import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default:
          "border-transparent bg-primary text-primary-foreground hover:bg-primary/80",
        secondary:
          "border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80",
        destructive:
          "border-transparent bg-destructive text-destructive-foreground hover:bg-destructive/80",
        outline: "text-foreground",
        "confidence-high":
          "border-transparent bg-[hsl(var(--confidence-high))] text-white hover:bg-[hsl(var(--confidence-high))]/80",
        "confidence-good":
          "border-transparent bg-[hsl(var(--confidence-good))] text-white hover:bg-[hsl(var(--confidence-good))]/80",
        "confidence-medium":
          "border-transparent bg-[hsl(var(--confidence-medium))] text-white hover:bg-[hsl(var(--confidence-medium))]/80",
        "confidence-low":
          "border-transparent bg-[hsl(var(--confidence-low))] text-white hover:bg-[hsl(var(--confidence-low))]/80",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  )
}

export { Badge, badgeVariants }
