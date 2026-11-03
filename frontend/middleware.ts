export { default } from "next-auth/middleware";

export const config = {
  // Protect everything except for authentication API routes and static assets
  matcher: [
    // The logo must load on the login page, before there's a session.
    "/((?!api/auth|auth/signin|_next/static|_next/image|favicon.ico|lanca-logo.png|\\.swa).*)",
  ],
};
