<script>
	import '@evidence-dev/tailwind/fonts.css';
	import '../app.css';
	import { EvidenceDefaultLayout } from '@evidence-dev/core-components';
	export let data;
</script>

<EvidenceDefaultLayout
	{data}
	title="MarketScope"
	homePageName="Overview"
	githubRepo="https://github.com/Aaron-Darcy/MarketScope"
	maxWidth={1180}
	hideTOC={true}
	neverShowQueries={true}
	builtWithEvidence={false}
>
	<slot slot="content" />
</EvidenceDefaultLayout>
