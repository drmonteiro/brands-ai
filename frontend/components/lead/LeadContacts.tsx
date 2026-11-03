import { Linkedin, Mail, Phone } from "lucide-react";
import { getCompanyLinkedIn, getContacts } from "@/lib/lead";
import { BrandLead } from "@/lib/types";

const linkClass = "inline-flex items-center gap-1.5 text-[12px] text-muted-foreground hover:text-foreground hover:underline";

export function LeadContacts({ lead }: { lead: BrandLead }) {
  const contacts = getContacts(lead);
  const companyLinkedIn = getCompanyLinkedIn(lead);
  const email = lead.contact_email || lead.contactEmail || "";
  const phone = lead.contact_phone || lead.contactPhone || "";
  const name = lead.contact_name || lead.contactName || "";
  const role = lead.contact_role || lead.contactRole || "";

  if (!contacts.length && !companyLinkedIn && !email && !phone && !name) return null;

  return (
    <div className="space-y-2">
      {contacts.length > 0 && (
        <ul className="space-y-1.5">
          {contacts.map((contact) => (
            <li key={contact.linkedin_url}>
              <a
                href={contact.linkedin_url}
                target="_blank"
                rel="noopener noreferrer"
                className="group flex items-baseline gap-2 text-[13px]"
              >
                <Linkedin className="h-3.5 w-3.5 flex-shrink-0 translate-y-0.5 text-[#0A66C2]" aria-hidden />
                <span className="min-w-0">
                  <span className="font-medium text-foreground group-hover:underline">{contact.name}</span>
                  {contact.role && <span className="text-muted-foreground"> · {contact.role}</span>}
                </span>
              </a>
            </li>
          ))}
        </ul>
      )}
      {contacts.length === 0 && name && (
        <p className="text-[13px] font-medium text-foreground">
          {name}
          {role && <span className="font-normal text-muted-foreground"> · {role}</span>}
        </p>
      )}
      {(companyLinkedIn || email || phone) && (
        <div className="flex flex-wrap gap-x-4 gap-y-1">
          {companyLinkedIn && (
            <a href={companyLinkedIn} target="_blank" rel="noopener noreferrer" className={linkClass}>
              <Linkedin className="h-3.5 w-3.5" aria-hidden /> Página da empresa
            </a>
          )}
          {email && (
            <a href={`mailto:${email}`} className={`${linkClass} min-w-0 break-all`}>
              <Mail className="h-3.5 w-3.5 flex-shrink-0" aria-hidden /> {email}
            </a>
          )}
          {phone && (
            <a href={`tel:${phone}`} className={linkClass}>
              <Phone className="h-3.5 w-3.5" aria-hidden /> {phone}
            </a>
          )}
        </div>
      )}
    </div>
  );
}
