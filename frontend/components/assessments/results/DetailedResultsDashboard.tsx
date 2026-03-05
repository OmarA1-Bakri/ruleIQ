'use client';

import { useState } from 'react';
import { Calendar, TrendingUp, CheckCircle, Clock, Target } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ComplianceScoreGauge } from './compliance-score-gauge';
import { GapAnalysisChart } from './gap-analysis-chart';
import { RecommendationsList } from './recommendations-list';
import { TrendAnalysisChart } from './TrendAnalysisChart';
import { SectionScorecard } from './SectionScorecard';
import { ExportButton } from './ExportButton';
import { AssessmentResult } from '@/lib/assessment-engine/types';
import { TrendDataPoint, SectionScoreDetail } from '@/types/assessment-results';

// Helper function to format section names from IDs
const formatSectionName = (id: string): string => {
  // Handle kebab-case, snake_case, and camelCase
  return id
    // Convert kebab-case to spaces
    .replace(/-/g, ' ')
    // Convert snake_case to spaces
    .replace(/_/g, ' ')
    // Convert camelCase to spaces (but preserve existing spaces)
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    // Capitalize each word
    .split(' ')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');
};

interface DetailedResultsDashboardProps {
  results: AssessmentResult;  // Only accept AssessmentResult format
  sectionDetails?: SectionScoreDetail[];
  trendData?: TrendDataPoint[];

  isExporting?: boolean;
  className?: string;
}


export function DetailedResultsDashboard({
  results,
  sectionDetails = [],
  trendData = [],

  isExporting: _isExporting = false,
  className = ''
}: DetailedResultsDashboardProps) {
  const [activeTab, setActiveTab] = useState('overview');
  
  // Helper function to normalize section identifiers for consistent mapping
  const normalizeSectionId = (id: string): string => {
    return id
      .toLowerCase()
      .replace(/\s+/g, '_')
      .replace(/-/g, '_')
      .replace(/[^a-z0-9_]/g, '');
  };
  
  // Directly use results (AssessmentResult format)
  const { overallScore, gaps, recommendations, sectionScores, completedAt } = results;
  const completedDate = typeof completedAt === 'string' ? new Date(completedAt) : completedAt;

  // Calculate provisional completion percentage for section details generation
  // This will be recalculated more accurately after sections are determined
  const provisionalCompletionPercentage = sectionDetails.length > 0 
    ? Math.round((sectionDetails.filter(s => s.completionStatus === 'complete').length / sectionDetails.length) * 100)
    : 100; // Default to 100 if no sections provided

  // Generate default section details if not provided
  // Use deterministic counts based on completion percentage and section scores
  const defaultSectionDetails: SectionScoreDetail[] = Object.entries(sectionScores).map(([id, score]) => {
    // NOTE: These are estimated values when actual section data is not available
    // In production, these should be derived from actual assessment framework data
    // Consider showing an "estimated" badge in the UI for these values
    const _sectionCount = Object.keys(sectionScores).length || 5; // Default to 5 sections
    const totalQuestionsPerSection = 10; // Estimated standard questions per section

    // Calculate questions answered based on completion percentage and score
    const questionsAnswered = provisionalCompletionPercentage < 100
      ? Math.floor((provisionalCompletionPercentage / 100) * totalQuestionsPerSection)
      : Math.round((score / 100) * totalQuestionsPerSection);

    return {
      sectionId: id,
      sectionName: formatSectionName(id),
      sectionDescription: `Assessment for ${formatSectionName(id)}`,
      score,
      maxScore: 100,
      percentage: score,
      totalQuestions: totalQuestionsPerSection,
      answeredQuestions: questionsAnswered,
      skippedQuestions: totalQuestionsPerSection - questionsAnswered,
      completionStatus: provisionalCompletionPercentage >= 100 ? 'complete' : provisionalCompletionPercentage > 50 ? 'partial' : 'not_started',
      riskLevel: score >= 80 ? 'low' : score >= 60 ? 'medium' : score >= 40 ? 'high' : 'critical',
      strengths: score >= 60 ? ['Good implementation practices', 'Adequate documentation'] : [],
      weaknesses: score < 80 ? ['Enhanced monitoring needed', 'Regular reviews required'] : [],
      keyFindings: [],
      questionBreakdown: [],
      sectionRecommendations: [],
      sectionGaps: [],
      historicalScores: []
    } as SectionScoreDetail;
  });

  const sectionsToDisplay = sectionDetails.length > 0 ? sectionDetails : defaultSectionDetails;
  const isUsingEstimatedData = sectionDetails.length === 0;

  // Calculate completion percentage from sections data
  const completedSections = sectionsToDisplay.filter(s => s.completionStatus === 'complete').length;
  const completionPercentage = sectionsToDisplay.length > 0
    ? Math.round((completedSections / sectionsToDisplay.length) * 100)
    : 100; // Default to 100 if no sections

  // Calculate summary statistics
  const totalQuestions = sectionsToDisplay.reduce((sum, section) => sum + section.totalQuestions, 0);
  const answeredQuestions = sectionsToDisplay.reduce((sum, section) => sum + section.answeredQuestions, 0);
  const nextAssessmentDate = new Date(completedDate);
  nextAssessmentDate.setMonth(nextAssessmentDate.getMonth() + 6);

  // Prepare gap analysis data
  const gapAnalysisData = sectionsToDisplay.map(section => ({
    name: section.sectionName,
    score: section.score
  }));

  // Transform recommendations for display
  const displayRecommendations = recommendations.map(rec => {
    let priority: "High" | "Medium" | "Low";
    switch (rec.priority) {
      case 'immediate':
      case 'short_term':
        priority = 'High';
        break;
      case 'medium_term':
        priority = 'Medium';
        break;
      default:
        priority = 'Low';
    }
    return {
      id: rec.id,
      text: rec.description,
      priority
    };
  });

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Header with Export Buttons */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Assessment Results</h1>
          <p className="text-muted-foreground">
            Completed on {completedDate.toLocaleDateString()}
          </p>
        </div>
        <ExportButton
          results={results}
          trendData={trendData}
          estimatedBreakdown={isUsingEstimatedData}
        />
      </div>

      {/* Summary Statistics Panel */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center gap-2">
              <CheckCircle className="h-5 w-5 text-purple-600" />
              <div>
                <p className="text-sm font-medium text-muted-foreground">Questions Answered</p>
                <p className="text-2xl font-bold">{answeredQuestions}/{totalQuestions}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center gap-2">
              <Target className="h-5 w-5 text-purple-600" />
              <div>
                <p className="text-sm font-medium text-muted-foreground">Completion</p>
                <p className="text-2xl font-bold">{Math.round(completionPercentage)}%</p>
              </div>
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center gap-2">
              <Calendar className="h-5 w-5 text-purple-600" />
              <div>
                <p className="text-sm font-medium text-muted-foreground">Assessment Date</p>
                <p className="text-sm font-bold">{completedDate.toLocaleDateString()}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center gap-2">
              <Clock className="h-5 w-5 text-purple-600" />
              <div>
                <p className="text-sm font-medium text-muted-foreground">Next Assessment</p>
                <p className="text-sm font-bold">{nextAssessmentDate.toLocaleDateString()}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Main Dashboard Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="sections">Section Details</TabsTrigger>
          <TabsTrigger value="gaps">Gaps & Recommendations</TabsTrigger>
          <TabsTrigger value="trends">Trends</TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-6">
          <div className="grid gap-6 lg:grid-cols-2">
            {/* Compliance Score Gauge */}
            <Card>
              <CardHeader>
                <CardTitle>Overall Compliance Score</CardTitle>
                <CardDescription>
                  Your current compliance level based on assessment responses
                </CardDescription>
              </CardHeader>
              <CardContent className="flex justify-center">
                <div id="compliance-gauge-chart">
                  <ComplianceScoreGauge score={overallScore} />
                </div>
              </CardContent>
            </Card>

            {/* Quick Stats */}
            <Card>
              <CardHeader>
                <CardTitle>Assessment Summary</CardTitle>
                <CardDescription>Key metrics from your assessment</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex justify-between">
                  <span className="text-sm font-medium">Risk Level</span>
                  <span className={`text-sm font-bold ${
                    overallScore >= 80 ? 'text-green-600' :
                    overallScore >= 60 ? 'text-yellow-600' :
                    'text-red-600'
                  }`}>
                    {overallScore >= 80 ? 'Low' : overallScore >= 60 ? 'Medium' : 'High'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm font-medium">Critical Gaps</span>
                  <span className="text-sm font-bold text-red-600">
                    {gaps.filter(gap => gap.severity === 'critical').length}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm font-medium">High Priority Items</span>
                  <span className="text-sm font-bold text-orange-600">
                    {recommendations.filter(rec => rec.priority === 'immediate' || rec.priority === 'short_term').length}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm font-medium">Sections Completed</span>
                  <span className="text-sm font-bold">
                    {sectionsToDisplay.filter(s => s.completionStatus === 'complete').length}/{sectionsToDisplay.length}
                  </span>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Gap Analysis Overview */}
          {gapAnalysisData.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Section Performance Overview</CardTitle>
                <CardDescription>
                  Performance breakdown across different assessment areas
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div id="gap-analysis-chart-overview">
                  <GapAnalysisChart data={gapAnalysisData} />
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Section Details Tab */}
        <TabsContent value="sections" className="space-y-6">
          {/* Show estimated badge if using heuristic data */}
          {isUsingEstimatedData && (
            <div className="flex items-center gap-2 p-3 bg-amber-50 border border-amber-200 rounded-lg">
              <span className="px-2 py-1 text-xs font-medium text-amber-800 bg-amber-100 rounded">
                Estimated
              </span>
              <p className="text-sm text-amber-700">
                Detailed breakdown is estimated based on overall scores. Complete a full assessment for precise metrics.
              </p>
            </div>
          )}
          <div className="space-y-6">
            {sectionsToDisplay.map((section, index) => {
              // Transform section data to SectionScorecard format
              const scorecardData = {
                section: {
                  id: section.sectionId,
                  title: section.sectionName,
                  description: section.sectionDescription || `Assessment section covering ${section.sectionName.toLowerCase()} compliance requirements`,
                  questions: [],
                  order: index
                },
                score: section.score,
                maxScore: section.maxScore || 100,
                questionsAnswered: section.answeredQuestions,
                totalQuestions: section.totalQuestions,
                completionStatus: section.completionStatus,
                riskLevel: section.riskLevel,
                strengths: section.strengths,
                improvements: section.weaknesses,
                questionDetails: [],
                // Add missing required properties with defaults
                answeredQuestions: section.answeredQuestions || 0,
                skippedQuestions: Math.max(0, (section.totalQuestions || 0) - (section.answeredQuestions || 0)),
                weaknesses: section.weaknesses || [],
                keyFindings: section.keyFindings || [],
                compliancePercentage: Math.round((section.score / (section.maxScore || 100)) * 100),
                criticalGaps: gaps.filter(gap => {
                  const normalizedGapSection = gap.section ? normalizeSectionId(gap.section) : '';
                  const normalizedGapCategory = gap.category ? normalizeSectionId(gap.category) : '';
                  const normalizedSectionId = normalizeSectionId(section.sectionId);
                  const normalizedSectionName = normalizeSectionId(section.sectionName);
                  return (normalizedGapSection === normalizedSectionId || 
                         normalizedGapCategory === normalizedSectionId ||
                         normalizedGapCategory === normalizedSectionName) && gap.severity === 'critical';
                }).length,
                recommendations: recommendations.filter(rec => {
                  const normalizedRecCategory = rec.category ? normalizeSectionId(rec.category) : '';
                  const normalizedSectionId = normalizeSectionId(section.sectionId);
                  const normalizedSectionName = normalizeSectionId(section.sectionName);
                  return normalizedRecCategory === normalizedSectionId || 
                         normalizedRecCategory === normalizedSectionName;
                }).slice(0, 3), // Limit to top 3 recommendations
                // Add final missing required properties
                questionBreakdown: section.questionBreakdown || [],
                sectionRecommendations: recommendations.filter(rec => {
                  const normalizedRecCategory = rec.category ? normalizeSectionId(rec.category) : '';
                  const normalizedSectionId = normalizeSectionId(section.sectionId);
                  const normalizedSectionName = normalizeSectionId(section.sectionName);
                  return normalizedRecCategory === normalizedSectionId || 
                         normalizedRecCategory === normalizedSectionName;
                }),
                sectionGaps: gaps.filter(gap => {
                  const normalizedGapSection = gap.section ? normalizeSectionId(gap.section) : '';
                  const normalizedGapCategory = gap.category ? normalizeSectionId(gap.category) : '';
                  const normalizedSectionId = normalizeSectionId(section.sectionId);
                  const normalizedSectionName = normalizeSectionId(section.sectionName);
                  return normalizedGapSection === normalizedSectionId || 
                         normalizedGapCategory === normalizedSectionId ||
                         normalizedGapCategory === normalizedSectionName;
                }),
                historicalScores: section.historicalScores || [],
                relatedGaps: gaps.filter(gap => {
                  const normalizedGapSection = gap.section ? normalizeSectionId(gap.section) : '';
                  const normalizedGapCategory = gap.category ? normalizeSectionId(gap.category) : '';
                  const normalizedSectionId = normalizeSectionId(section.sectionId);
                  const normalizedSectionName = normalizeSectionId(section.sectionName);
                  return normalizedGapSection === normalizedSectionId || 
                         normalizedGapCategory === normalizedSectionId ||
                         normalizedGapCategory === normalizedSectionName;
                }),
                relatedRecommendations: recommendations.filter(rec => {
                  const normalizedRecCategory = rec.category ? normalizeSectionId(rec.category) : '';
                  const normalizedSectionId = normalizeSectionId(section.sectionId);
                  const normalizedSectionName = normalizeSectionId(section.sectionName);
                  return normalizedRecCategory === normalizedSectionId || 
                         normalizedRecCategory === normalizedSectionName;
                })
              };
              
              return (
                <SectionScorecard
                  key={section.sectionId}
                  scorecard={scorecardData}
                  defaultExpanded={false}
                  isEstimated={isUsingEstimatedData}
                />
              );
            })}
          </div>
        </TabsContent>

        {/* Gaps & Recommendations Tab */}
        <TabsContent value="gaps" className="space-y-6">
          <div className="grid gap-6 lg:grid-cols-2">
            {/* Gap Analysis Chart */}
            <Card>
              <CardHeader>
                <CardTitle>Gap Analysis</CardTitle>
                <CardDescription>
                  Areas requiring attention based on your responses
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div id="gap-analysis-chart-gaps">
                  <GapAnalysisChart data={gapAnalysisData} />
                </div>
              </CardContent>
            </Card>

            {/* Gap Summary */}
            <Card>
              <CardHeader>
                <CardTitle>Gap Summary</CardTitle>
                <CardDescription>Breakdown of identified compliance gaps</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {['critical', 'high', 'medium', 'low'].map((severity) => {
                  const count = gaps.filter(gap => gap.severity === severity).length;
                  return (
                    <div key={severity} className="flex justify-between items-center">
                      <span className="text-sm font-medium capitalize">{severity} Risk</span>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-bold">{count}</span>
                        <div className={`h-2 w-8 rounded-full ${
                          severity === 'critical' ? 'bg-red-500' :
                          severity === 'high' ? 'bg-orange-500' :
                          severity === 'medium' ? 'bg-yellow-500' :
                          'bg-green-500'
                        }`} />
                      </div>
                    </div>
                  );
                })}
              </CardContent>
            </Card>
          </div>

          {/* Recommendations */}
          <Card>
            <CardHeader>
              <CardTitle>Recommendations</CardTitle>
              <CardDescription>
                Prioritized actions to improve your compliance posture
              </CardDescription>
            </CardHeader>
            <CardContent>
              <RecommendationsList recommendations={displayRecommendations} />
            </CardContent>
          </Card>
        </TabsContent>

        {/* Trends Tab */}
        <TabsContent value="trends" className="space-y-6">
          {trendData.length > 0 ? (
            <Card>
              <CardHeader>
                <CardTitle>Score Trends</CardTitle>
                <CardDescription>
                  Track your compliance score progress over time
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div id="trend-analysis-chart">
                  <TrendAnalysisChart
                    data={trendData}
                  />
                </div>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardHeader>
                <CardTitle>No Historical Data</CardTitle>
                <CardDescription>
                  Complete more assessments to see trend analysis
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="text-center py-12">
                  <TrendingUp className="h-12 w-12 text-muted-foreground/50 mx-auto mb-4" />
                  <h3 className="text-lg font-semibold mb-2">Start Building Your Trend History</h3>
                  <p className="text-muted-foreground mb-4">
                    Take regular assessments to track your compliance progress over time.
                  </p>
                  <Button variant="outline">
                    Schedule Next Assessment
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}