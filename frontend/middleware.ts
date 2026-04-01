export { default } from "next-auth/middleware";

export const config = {
  // Protect everything except for authentication API routes and static assets
  matcher: [
    "/((?!api/auth|auth/signin|_next/static|_next/image|favicon.ico).*)",
  ],
};
