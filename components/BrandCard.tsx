"use client";

import { useState } from "react";
import { BrandLead } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { 
  ExternalLink, 
  CheckCircle2, 
  Loader2, 
  Mail, 
  MapPin, 
  Store, 
  DollarSign,
  Shirt,
  Building2,
  ChevronDown,
  ChevronUp,
  Sparkles
} from "lucide-react";

interface BrandCardProps {
  brand: BrandLead;
  onSendEmail: (brand: BrandLead) => Promise<void>;
}

export function BrandCard({ brand, onSendEmail }: BrandCardProps) {
  const [emailStatus, setEmailStatus] = useState<"idle" | "sending" | "sent">("idle");
  const [isExpanded, setIsExpanded] = useState(false);
  
  const handleSendEmail = async () => {
    setEmailStatus("sending");
    try {
      await onSendEmail(brand);
      setEmailStatus("sent");
    } catch (error) {
      console.error("Failed to send email:", error);
      setEmailStatus("idle");
      alert("Failed to send email. Please try again.");
    }
  };
  
  const hasDetails = brand.companyOverview && brand.companyOverview !== "Informação não disponível";
  const hasVerificationLog = brand.verificationLog && brand.verificationLog.length > 0;
  
  return (
    <div className="group bg-white rounded-2xl border border-lanca-black/5 shadow-soft hover:shadow-elevated transition-all duration-500 overflow-hidden">
      {/* Main Content */}
      <div className="p-6 md:p-8">
        {/* Header Row */}
        <div className="flex flex-col md:flex-row md:items-start gap-6">
          {/* Brand Info */}
          <div className="flex-1 min-w-0">
            {/* Brand Name & Link */}
            <div className="flex items-start gap-3 mb-4">
              <div className="flex-1 min-w-0">
                <h3 className="font-serif text-2xl md:text-3xl text-lanca-black group-hover:text-lanca-blackLight transition-colors truncate">
                  {brand.name}
                </h3>
                <a 
                  href={brand.websiteUrl} 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 text-sm text-lanca-warmGray hover:text-lanca-black transition-colors mt-1"
                >
                  <span className="truncate max-w-[280px]">{brand.websiteUrl}</span>
                  <ExternalLink className="h-3 w-3 flex-shrink-0" />
                </a>
              </div>
              
              {/* Origin Badge */}
              {brand.originCountry && brand.originCountry !== "USA" && brand.originCountry !== "Unknown" && (
                <Badge variant="outline" className="flex-shrink-0 bg-blue-50 border-blue-200 text-blue-700 text-xs">
                  {brand.originCountry}
                </Badge>
              )}
            </div>
            
            {/* Quick Stats Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {/* Store Count */}
              <div className="flex items-center gap-2.5 p-3 bg-lanca-cream/50 rounded-xl">
                <div className="p-1.5 bg-white rounded-lg shadow-inner-soft">
                  <Store className="h-4 w-4 text-lanca-black" />
                </div>
                <div>
                  <p className="text-lg font-semibold text-lanca-black">{brand.storeCount}</p>
                  <p className="text-2xs text-lanca-warmGray">Stores</p>
                </div>
              </div>
              
              {/* Average Price */}
              <div className={`flex items-center gap-2.5 p-3 rounded-xl ${
                brand.averageSuitPriceUSD > 0 
                  ? 'bg-lanca-yellow/10' 
                  : 'bg-lanca-cream/50'
              }`}>
                <div className={`p-1.5 rounded-lg shadow-inner-soft ${
                  brand.averageSuitPriceUSD > 0 
                    ? 'bg-lanca-yellow/20' 
                    : 'bg-white'
                }`}>
                  <DollarSign className={`h-4 w-4 ${
                    brand.averageSuitPriceUSD > 0 
                      ? 'text-lanca-yellowDark' 
                      : 'text-lanca-warmGray'
                  }`} />
                </div>
                <div>
                  {brand.averageSuitPriceUSD > 0 ? (
                    <>
                      <p className="text-lg font-semibold text-lanca-black">${brand.averageSuitPriceUSD.toFixed(0)}</p>
                      <p className="text-2xs text-lanca-warmGray">Avg. Suit</p>
                    </>
                  ) : (
                    <>
                      <p className="text-sm font-medium text-lanca-warmGray">N/A</p>
                      <p className="text-2xs text-lanca-warmGray">On Request</p>
                    </>
                  )}
                </div>
              </div>
              
              {/* Revenue if available */}
              {brand.revenue && (
                <div className="flex items-center gap-2.5 p-3 bg-green-50/80 rounded-xl">
                  <div className="p-1.5 bg-white rounded-lg shadow-inner-soft">
                    <Building2 className="h-4 w-4 text-green-600" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-green-700">{brand.revenue}</p>
                    <p className="text-2xs text-green-600/70">Revenue</p>
                  </div>
                </div>
              )}
              
              {/* Target Segment */}
              {brand.targetGender && (
                <div className="flex items-center gap-2.5 p-3 bg-blue-50/80 rounded-xl">
                  <div className="p-1.5 bg-white rounded-lg shadow-inner-soft">
                    <Shirt className="h-4 w-4 text-blue-600" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-blue-700">{brand.targetGender}</p>
                    <p className="text-2xs text-blue-600/70">Segment</p>
                  </div>
                </div>
              )}
            </div>
          </div>
          
          {/* Action Button - Desktop */}
          <div className="hidden md:block flex-shrink-0">
            <Button
              className={`min-w-[200px] h-12 font-medium rounded-xl transition-all duration-300 ${
                emailStatus === "idle" 
                  ? "bg-lanca-black hover:bg-lanca-charcoal text-white hover:shadow-lg" 
                  : emailStatus === "sending"
                  ? "bg-lanca-black/80 text-white cursor-wait"
                  : "bg-green-600 text-white hover:bg-green-700"
              }`}
              onClick={handleSendEmail}
              disabled={emailStatus !== "idle"}
            >
              {emailStatus === "idle" && (
                <>
                  <Mail className="h-4 w-4 mr-2" />
                  Send Partnership Email
                </>
              )}
              {emailStatus === "sending" && (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Sending...
                </>
              )}
              {emailStatus === "sent" && (
                <>
                  <CheckCircle2 className="h-4 w-4 mr-2" />
                  Email Sent!
                </>
              )}
            </Button>
          </div>
        </div>
        
        {/* Clothing Types */}
        {brand.clothingTypes && brand.clothingTypes.length > 0 && brand.clothingTypes[0] !== "Unknown" && (
          <div className="mt-6 pt-6 border-t border-lanca-black/5">
            <div className="flex flex-wrap gap-2">
              {brand.clothingTypes.map((type, idx) => (
                <Badge 
                  key={idx} 
                  variant="outline" 
                  className="text-xs bg-white border-lanca-black/10 text-lanca-black hover:border-lanca-yellow/50 transition-colors"
                >
                  {type}
                </Badge>
              ))}
              
              {brand.businessModel && brand.businessModel !== "Unknown" && (
                <Badge className="text-xs bg-lanca-yellow/10 border-lanca-yellow/20 text-lanca-black">
                  {brand.businessModel}
                </Badge>
              )}
            </div>
          </div>
        )}
        
        {/* Location */}
        {brand.city && (
          <div className="flex items-center gap-2 mt-4 text-sm text-lanca-warmGray">
            <MapPin className="h-3.5 w-3.5" />
            <span>{brand.city}</span>
            {brand.originCountry && brand.originCountry !== "Unknown" && (
              <span>, {brand.originCountry}</span>
            )}
          </div>
        )}
        
        {/* Action Button - Mobile */}
        <div className="mt-6 md:hidden">
          <Button
            className={`w-full h-12 font-medium rounded-xl transition-all duration-300 ${
              emailStatus === "idle" 
                ? "bg-lanca-black hover:bg-lanca-charcoal text-white" 
                : emailStatus === "sending"
                ? "bg-lanca-black/80 text-white cursor-wait"
                : "bg-green-600 text-white hover:bg-green-700"
            }`}
            onClick={handleSendEmail}
            disabled={emailStatus !== "idle"}
          >
            {emailStatus === "idle" && (
              <>
                <Mail className="h-4 w-4 mr-2" />
                Send Partnership Email
              </>
            )}
            {emailStatus === "sending" && (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Sending...
              </>
            )}
            {emailStatus === "sent" && (
              <>
                <CheckCircle2 className="h-4 w-4 mr-2" />
                Email Sent!
              </>
            )}
          </Button>
        </div>
      </div>
      
      {/* Expandable Details Section */}
      {(hasDetails || hasVerificationLog) && (
        <>
          {/* Expand Toggle */}
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="w-full px-6 md:px-8 py-3 flex items-center justify-center gap-2 bg-lanca-cream/30 hover:bg-lanca-cream/50 border-t border-lanca-black/5 transition-colors text-sm text-lanca-warmGray"
          >
            <span>{isExpanded ? "Show less" : "Show more details"}</span>
            {isExpanded ? (
              <ChevronUp className="h-4 w-4" />
            ) : (
              <ChevronDown className="h-4 w-4" />
            )}
          </button>
          
          {/* Expanded Content */}
          {isExpanded && (
            <div className="px-6 md:px-8 pb-6 md:pb-8 border-t border-lanca-black/5 bg-lanca-cream/20 animate-fade-in">
              {/* Company Overview */}
              {hasDetails && (
                <div className="pt-6">
                  <div className="flex items-center gap-2 mb-3">
                    <Sparkles className="h-4 w-4 text-lanca-yellow" />
                    <h4 className="text-sm font-semibold text-lanca-black">About the Company</h4>
                  </div>
                  <p className="text-sm text-lanca-warmGray leading-relaxed">
                    {brand.companyOverview}
                  </p>
                </div>
              )}
              
              {/* Verification Log */}
              {hasVerificationLog && (
                <div className={hasDetails ? "pt-6 mt-6 border-t border-lanca-black/5" : "pt-6"}>
                  <div className="flex items-center gap-2 mb-3">
                    <CheckCircle2 className="h-4 w-4 text-green-600" />
                    <h4 className="text-sm font-semibold text-lanca-black">Verification Details</h4>
                  </div>
                  <ul className="space-y-2">
                    {brand.verificationLog?.map((log, idx) => (
                      <li 
                        key={idx} 
                        className="flex items-start gap-2.5 text-sm text-lanca-warmGray"
                      >
                        <div className="mt-1 w-4 h-4 rounded-full bg-green-100 flex items-center justify-center flex-shrink-0">
                          <CheckCircle2 className="w-3 h-3 text-green-600" />
                        </div>
                        <span>{log}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
