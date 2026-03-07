import { Metadata } from 'next';
import AssessmentResultsClient from './client';

interface PageProps {
  params: Promise<{
    token: string;
  }>;
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  // Await params for Next.js 15 compatibility
  const { token } = await params;
  
  // Use static metadata to avoid server-side fetching latency
  // Dynamic metadata is non-critical for this page
  return {
    title: 'Compliance Assessment Results | ruleIQ',
    description: 'View your detailed compliance assessment results with personalized recommendations and improvement strategies.',
    openGraph: {
      title: 'Compliance Assessment Results | ruleIQ',
      description: 'Comprehensive compliance assessment analysis with risk scoring and actionable recommendations.',
      type: 'website',
      url: `${process.env.NEXT_PUBLIC_BASE_URL || ''}/assessment/results/${token}`,
    },
    twitter: {
      card: 'summary_large_image',
      title: 'Compliance Assessment Results | ruleIQ',
      description: 'View your compliance assessment results and get personalized recommendations.',
    }
  };
  
  // Previous implementation preserved for reference:
  // The following code fetched full results server-side which could cause latency/timeout issues
  // If dynamic metadata is needed in future, implement a lightweight summary endpoint
  /*
  try {
    // Note: This API call runs server-side during metadata generation
    // Consider using a lightweight summary endpoint or caching to optimize performance
    const results = await assessmentResultsService.getResults(params.token);
    const score = Math.round(results.compliance_score);

    // Derive risk level from risk_score
    const riskScore = results.risk_score;
    let riskLevel: string;
    if (riskScore >= 75) {
      riskLevel = 'critical';
    } else if (riskScore >= 50) {
      riskLevel = 'high';
    } else if (riskScore >= 25) {
      riskLevel = 'medium';
    } else {
      riskLevel = 'low';
    }

    return {
      title: `Compliance Assessment Results - ${score}% Score | ruleIQ`,
      description: `Your compliance assessment shows a ${score}% score with ${riskLevel} risk level. Get detailed insights and recommendations to improve your compliance posture.`,
      openGraph: {
        title: `My Compliance Assessment Results - ${score}% Score`,
        description: `I scored ${score}% on my compliance assessment with ruleIQ. Check out the detailed analysis and recommendations.`,
        type: 'website',
        url: `${process.env.NEXT_PUBLIC_BASE_URL || ''}/assessment/results/${params.token}`,
      },
      twitter: {
        card: 'summary_large_image',
        title: `Compliance Assessment Results - ${score}% Score`,
        description: `Detailed compliance assessment results with ${riskLevel} risk level and actionable recommendations.`,
      }
    };
  } catch (error) {
    // Default metadata if results cannot be loaded
    return {
      title: 'Assessment Results | ruleIQ',
      description: 'View your compliance assessment results and get personalized recommendations.',
    };
  }
  */
}

export default async function AssessmentResultsPage({ params }: PageProps) {
  // Await params for Next.js 15 compatibility
  const { token } = await params;
  return <AssessmentResultsClient token={token} />;
}
