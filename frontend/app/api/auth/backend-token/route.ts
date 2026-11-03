import { SignJWT } from "jose";
import { getToken } from "next-auth/jwt";
import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const TOKEN_LIFETIME_SECONDS = 15 * 60;

/** Exchanges a logged-in session for a short-lived token the backend API accepts. */
export async function GET(request: NextRequest) {
  const session = await getToken({ req: request, secret: process.env.NEXTAUTH_SECRET });
  if (!session?.sub) {
    return NextResponse.json({ detail: "Sessão inválida." }, { status: 401 });
  }

  const secret = process.env.BACKEND_JWT_SECRET;
  if (!secret) {
    return NextResponse.json({ detail: "Autenticação não configurada." }, { status: 503 });
  }

  const expiresAt = Math.floor(Date.now() / 1000) + TOKEN_LIFETIME_SECONDS;
  const token = await new SignJWT({ role: session.role ?? "lanca" })
    .setProtectedHeader({ alg: "HS256" })
    .setSubject(session.sub)
    .setIssuer("lanca-frontend")
    .setAudience("lanca-backend")
    .setIssuedAt()
    .setExpirationTime(expiresAt)
    .sign(new TextEncoder().encode(secret));

  return NextResponse.json({ token, expiresAt }, { headers: { "Cache-Control": "no-store" } });
}
