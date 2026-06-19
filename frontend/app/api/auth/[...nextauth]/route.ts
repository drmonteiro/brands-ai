import NextAuth, { type NextAuthOptions } from "next-auth";
import AzureADProvider from "next-auth/providers/azure-ad";
import CredentialsProvider from "next-auth/providers/credentials";

/**
 * External agents (e.g. the UK agent) sign in with a shared username/password
 * that we hand out manually. Configure via env:
 *
 *   EXTERNAL_AGENTS='[{"username":"uk-agent","password":"secret","name":"UK Agent","region":"UK"}]'
 *
 * or a single account fallback:
 *
 *   EXTERNAL_AGENT_USERNAME=uk-agent
 *   EXTERNAL_AGENT_PASSWORD=secret
 *   EXTERNAL_AGENT_NAME="UK Agent"
 *   EXTERNAL_AGENT_REGION=UK
 */
type ExternalAgent = {
  username: string;
  password: string;
  name?: string;
  region?: string;
  email?: string;
};

function getExternalAgents(): ExternalAgent[] {
  const raw = process.env.EXTERNAL_AGENTS;
  if (raw) {
    try {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        return parsed.filter((a) => a?.username && a?.password);
      }
    } catch {
      // fall through to single-account fallback
    }
  }
  const username = process.env.EXTERNAL_AGENT_USERNAME;
  const password = process.env.EXTERNAL_AGENT_PASSWORD;
  if (username && password) {
    return [
      {
        username,
        password,
        name: process.env.EXTERNAL_AGENT_NAME || "Agente Externo",
        region: process.env.EXTERNAL_AGENT_REGION,
      },
    ];
  }
  return [];
}

const authOptions: NextAuthOptions = {
  providers: [
    AzureADProvider({
      clientId: process.env.AZURE_AD_CLIENT_ID!,
      clientSecret: process.env.AZURE_AD_CLIENT_SECRET!,
      tenantId: process.env.AZURE_AD_TENANT_ID,
      authorization: {
        params: {
          scope: "openid profile email User.Read",
        },
      },
    }),
    CredentialsProvider({
      id: "external-agent",
      name: "Agente externo",
      credentials: {
        username: { label: "Utilizador", type: "text" },
        password: { label: "Palavra-passe", type: "password" },
      },
      async authorize(credentials) {
        if (!credentials?.username || !credentials?.password) return null;
        const inputUser = credentials.username.trim();
        const inputPass = credentials.password.trim();
        const agent = getExternalAgents().find(
          (a) => a.username === inputUser && a.password === inputPass
        );
        if (!agent) return null;
        return {
          id: `agent:${agent.username}`,
          name: agent.name || agent.username,
          email: agent.email || `${agent.username}@external.lanca`,
          role: "external_agent",
          region: agent.region,
        } as any;
      },
    }),
  ],
  // CredentialsProvider requires JWT-based sessions.
  session: { strategy: "jwt" },
  pages: {
    signIn: "/auth/signin",
  },
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.role = (user as any).role || "lanca";
        token.region = (user as any).region;
      }
      return token;
    },
    async session({ session, token }) {
      if (session.user) {
        (session.user as any).id = token.sub;
        (session.user as any).role = token.role || "lanca";
        (session.user as any).region = token.region;
      }
      return session;
    },
  },
  secret: process.env.NEXTAUTH_SECRET,
  trustHost: true,
};

const handler = NextAuth(authOptions);

export { handler as GET, handler as POST };
