/**
 * Landing Page - Main entry point
 * Using the RenovationTech Design System
 */
export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background">
      {/* Hero Section */}
      <section className="py-16 md:py-24">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center animate-in fade-in duration-700">
            {/* Logo/Brand */}
            <div className="mb-8">
              <h1 className="text-4xl md:text-5xl font-bold tracking-tight text-foreground mb-4">
                RenovationTech
              </h1>
              <div className="flex items-center justify-center gap-2 text-muted-foreground">
                <div className="h-px w-12 bg-border" />
                <p className="text-sm font-medium uppercase tracking-wide">
                  AI-Powered Renovation Platform
                </p>
                <div className="h-px w-12 bg-border" />
              </div>
            </div>

            {/* Hero Title */}
            <h2 className="text-3xl md:text-4xl lg:text-5xl font-bold tracking-tight text-foreground mb-6 max-w-4xl mx-auto">
              Know Your Renovation Cost{' '}
              <span className="text-accent">Before You Start</span>
            </h2>

            {/* Subtitle */}
            <p className="text-lg md:text-xl text-muted-foreground mb-12 max-w-2xl mx-auto leading-relaxed">
              Get a professional 3-tier estimate in minutes. Our AI Quantity Surveyor 
              analyzes your project and delivers contractor-grade estimates.
            </p>

            {/* CTA Buttons */}
            <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
              <a
                href="/estimate"
                className="inline-flex items-center justify-center px-8 py-4 bg-accent hover:bg-accent/90 text-accent-foreground font-semibold rounded-lg shadow-sm hover:shadow-md transition-all duration-200 hover:scale-105"
              >
                Get Free Estimate
                <svg
                  className="ml-2 w-5 h-5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M13 7l5 5m0 0l-5 5m5-5H6"
                  />
                </svg>
              </a>
              <a
                href="/marketplace"
                className="inline-flex items-center justify-center px-8 py-4 border-2 border-primary text-primary hover:bg-primary hover:text-primary-foreground font-semibold rounded-lg transition-all duration-200"
              >
                I'm a Contractor
              </a>
            </div>
          </div>

          {/* Trust Indicators */}
          <div className="mt-16 grid grid-cols-1 md:grid-cols-3 gap-8 max-w-4xl mx-auto">
            <div className="text-center p-6 rounded-xl bg-card border border-border hover:shadow-md transition-shadow">
              <div className="text-3xl font-bold text-accent mb-2">{'<60s'}</div>
              <div className="text-sm text-muted-foreground">To Get Estimate</div>
            </div>
            <div className="text-center p-6 rounded-xl bg-card border border-border hover:shadow-md transition-shadow">
              <div className="text-3xl font-bold text-accent mb-2">3-Tier</div>
              <div className="text-sm text-muted-foreground">Pricing Options</div>
            </div>
            <div className="text-center p-6 rounded-xl bg-card border border-border hover:shadow-md transition-shadow">
              <div className="text-3xl font-bold text-accent mb-2">AI-Powered</div>
              <div className="text-sm text-muted-foreground">Professional Accuracy</div>
            </div>
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section className="py-16 bg-muted/50">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          <h3 className="text-2xl md:text-3xl font-semibold text-center mb-12 text-foreground">
            How It Works
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {/* Step 1 */}
            <div className="text-center">
              <div className="w-12 h-12 rounded-full bg-accent text-accent-foreground font-bold text-xl flex items-center justify-center mx-auto mb-4">
                1
              </div>
              <h4 className="font-semibold text-lg mb-2 text-foreground">Chat with AI</h4>
              <p className="text-muted-foreground text-sm">
                Describe your project and upload photos
              </p>
            </div>
            {/* Step 2 */}
            <div className="text-center">
              <div className="w-12 h-12 rounded-full bg-accent text-accent-foreground font-bold text-xl flex items-center justify-center mx-auto mb-4">
                2
              </div>
              <h4 className="font-semibold text-lg mb-2 text-foreground">Get Estimate</h4>
              <p className="text-muted-foreground text-sm">
                Receive detailed 3-tier pricing instantly
              </p>
            </div>
            {/* Step 3 */}
            <div className="text-center">
              <div className="w-12 h-12 rounded-full bg-accent text-accent-foreground font-bold text-xl flex items-center justify-center mx-auto mb-4">
                3
              </div>
              <h4 className="font-semibold text-lg mb-2 text-foreground">Connect with Contractors</h4>
              <p className="text-muted-foreground text-sm">
                Your project appears in our marketplace
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-8 border-t border-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center text-sm text-muted-foreground">
          <p>&copy; 2024 RenovationTech. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
}
