# Icon alias tables — component name → glyph

**Never use vendor logos or trademark icons.** Map components to
concept glyphs via this table; unknown components get the nearest
concept or a plain box:

| Glyph | AWS | Azure | GCP | Generic |
|---|---|---|---|---|
| `gateway` | ALB/NLB, API GW | App Gateway, Front Door (routing) | Cloud Load Balancing | nginx, HAProxy, Kong |
| `waf` | AWS WAF, Shield | Front Door WAF | Cloud Armor | ModSecurity |
| `cdn` | CloudFront | Azure CDN | Cloud CDN | Fastly, Cloudflare |
| `dns` | Route 53 | Azure DNS | Cloud DNS | any DNS |
| `container` | ECS, Fargate | Container Apps, ACI | Cloud Run | Docker, Compose |
| `orchestrator` | EKS | AKS | GKE | Kubernetes, Nomad |
| `compute` | EC2 | VMs | Compute Engine | bare metal |
| `function` | Lambda | Functions | Cloud Functions | serverless |
| `database` | RDS, Aurora, DynamoDB | Azure SQL, Cosmos | Cloud SQL, Spanner | Postgres, MySQL |
| `cache` | ElastiCache | Azure Cache (Redis) | Memorystore | Redis, Memcached |
| `bucket` | S3 | Blob Storage | GCS | MinIO |
| `queue` | SQS, SNS, EventBridge | Service Bus, Event Grid | Pub/Sub | RabbitMQ, Kafka |
| `secrets` | Secrets Manager, KMS | Key Vault | Secret Manager | Vault |
| `identity` | IAM, Cognito | Entra ID | Cloud IAM | Auth0, Keycloak |
| `logs` | CloudWatch | Monitor, App Insights | Cloud Logging | Grafana, ELK |
| `pipeline` | CodePipeline | Azure DevOps | Cloud Build | GitHub Actions, GitLab CI |
| `scheduler` | EventBridge Scheduler | Logic Apps timer | Cloud Scheduler | cron |
| `lock` | PrivateLink, VPN | Private Link | Private Service Connect | WireGuard |
| `notify` | SES, SNS email | Comm. Services | — | SMTP, Resend, Twilio |
| `ai` | Bedrock | Azure OpenAI | Vertex AI | Anthropic API, LLMs |
| `search` | OpenSearch | AI Search | — | Elastic, Meilisearch |
| `api` | API endpoints | APIM | Apigee | REST/GraphQL services |
| `user-browser` / `mobile` | — | — | — | human actors, clients |

Web & app tech (map frameworks/libraries to these — never framework logos):

| Glyph | Maps from |
|---|---|
| `server` | backend services: Express, Fastify, Hono, FastAPI, Django, NestJS, Node services |
| `user-browser` | SPA/frontend apps: React, Next.js, Vite, Vue, Svelte (the built UI as the client) |
| `mobile` | React Native, Expo, Flutter, native apps |
| `realtime` | WebSockets, socket.io, Yjs/CRDT sync, Pusher, Ably, live subscriptions |
| `payment` | Stripe, Square, PayPal, billing services |
| `map` | Mapbox, Leaflet, Google Maps, geocoding |
| `chart` | dashboards/analytics UIs: Recharts, d3, Chart.js |
| `cube` | 3D/graphics: three.js, react-three-fiber, WebGL |
| `test` | test suites/QA gates: vitest, jest, Playwright, Cypress |
| `video` | media pipelines: Remotion, ffmpeg, streaming |
| `document` | generated documents: PDFs (ReportLab, pdf-lib), reports, exports |
| `print` | print production, press pipelines, CMYK output |
| `image` | media storage/processing: uploads, thumbnails, image CDNs |
| `font` | typography systems, font services, @font-face pipelines |
| `plug` | integrations/plugins: MCP servers, SDKs, third-party API adapters |
| `terminal` | CLI tools, shells, dev tooling |
| `git` | repos, branches, version control |
| `webhook` | callbacks: Stripe/partner webhooks, event notifications, return URLs |

BaaS platforms compose: Supabase/Firebase = `database` + `bucket` +
`identity` as separate nodes (or one `database` node labelled with the
platform name when it plays a single role).
