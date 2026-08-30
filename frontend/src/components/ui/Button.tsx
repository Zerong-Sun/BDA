import { Button as ButtonPrimitive } from "@base-ui/react/button"
import type { VariantProps } from "class-variance-authority"
import * as React from "react"

import { buttonVariants } from "@/components/ui/button-variants"
import { cn } from "@/lib/utils"

function Button({
  className,
  variant = "default",
  size = "default",
  render,
  nativeButton,
  ...props
}: ButtonPrimitive.Props & VariantProps<typeof buttonVariants>) {
  const renderProps = React.isValidElement(render)
    ? (render.props as Record<string, unknown>)
    : null
  const isLinkRender = Boolean(
    renderProps && ("href" in renderProps || "to" in renderProps)
  )
  const resolvedRender =
    isLinkRender && React.isValidElement<{ role?: string }>(render)
      ? React.cloneElement(render, { role: render.props.role ?? "link" })
      : render
  const inferredNativeButton =
    render === undefined ||
    (React.isValidElement(render) && render.type === "button")

  return (
    <ButtonPrimitive
      data-slot="button"
      className={cn(buttonVariants({ variant, size, className }))}
      render={resolvedRender}
      nativeButton={nativeButton ?? inferredNativeButton}
      {...props}
    />
  )
}

const LinkButton = React.forwardRef<
  HTMLAnchorElement,
  React.ComponentPropsWithoutRef<"a"> &
    VariantProps<typeof buttonVariants>
>(function LinkButton(
  { className, variant = "default", size = "default", ...props },
  ref
) {
  return (
    <a
      ref={ref}
      data-slot="button"
      data-variant={variant}
      data-size={size}
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
})

export { Button, LinkButton }
