<script lang="ts">
	import { onMount } from 'svelte';
	import { appState, type Word, TIME_FILTERS } from '$lib/appState.svelte.ts';

	onMount(async () => {
		try {
			await appState.loadTerms();
		} catch (error) {
			console.error('Fetch failed:', error);
			appState.words = [
				{
					id: 999,
					term: 'Backend Disconnected',
					category: 'Error',
					date: new Date().toISOString(),
					definition: 'Make sure Docker is running!'
				}
			];
		}
	});
</script>

<main class="relative h-screen w-full overflow-hidden bg-slate-950 font-sans text-white">
	<div class="pointer-events-none absolute inset-0 flex items-center justify-center">
		<h1 class="select-none text-[20vw] font-black text-white/[0.03]">AURA</h1>
	</div>

	<div class="absolute left-1/2 top-8 z-40 flex w-11/12 max-w-5xl -translate-x-1/2 items-center gap-4 rounded-2xl border border-white/10 bg-white/5 p-4 shadow-2xl backdrop-blur-xl">
		<input
			type="text"
			placeholder="Search terms..."
			bind:value={appState.searchQuery}
			class="flex-1 rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-white placeholder-slate-400 outline-none transition-colors focus:border-cyan-500 focus:bg-white/10"
		/>
		<select
			bind:value={appState.selectedCategory}
			class="rounded-lg border border-white/10 bg-slate-800 px-4 py-2 text-white outline-none focus:border-cyan-500"
		>
			<option value={null}>All Categories</option>
			{#each appState.dynamicCategories as category}
				<option value={category}>{category}</option>
			{/each}
		</select>

		<div class="flex min-w-[300px] items-center gap-4 rounded-lg border border-white/10 bg-white/5 px-4 py-2">
			<span class="w-24 whitespace-nowrap text-right font-mono text-xs text-cyan-400">
				{TIME_FILTERS[appState.timeRangeIndex].label}
			</span>

			<input
				type="range"
				min="0"
				max={TIME_FILTERS.length - 1}
				step="1"
				bind:value={appState.timeRangeIndex}
				class="w-full cursor-pointer accent-cyan-500"
			/>
		</div>
	</div>

	<div class="relative z-10 flex h-full flex-col justify-center gap-12 overflow-hidden py-20">
		<div class="river-row animate-river" style="--duration: {Math.max(appState.filteredWords.length * 10, 120)}s;">
			{#each [...appState.filteredWords, ...appState.filteredWords] as word}
				<button onclick={() => appState.selectWord(word)} class="group relative flex flex-col items-start gap-1 rounded-2xl border border-white/10 bg-white/5 p-6 backdrop-blur-md transition-all hover:scale-105 hover:border-cyan-500/50 hover:bg-white/10">
					<span class="text-xs font-mono uppercase tracking-widest text-cyan-400 opacity-70">{word.category}</span>
					<span class="text-2xl font-bold tracking-tight">{word.term}</span>
					<div class="absolute inset-0 -z-10 rounded-2xl bg-cyan-500/0 blur-xl transition-all group-hover:bg-cyan-500/10"></div>
				</button>
			{/each}
		</div>

		<div class="river-row animate-river" style="--duration: {Math.max(appState.filteredWords.length * 12, 160)}s;">
			{#each [...appState.filteredWords, ...appState.filteredWords].reverse() as word}
				<button onclick={() => appState.selectWord(word)} class="group relative flex flex-col items-start gap-1 rounded-2xl border border-white/10 bg-white/5 p-6 backdrop-blur-md transition-all hover:scale-105 hover:border-cyan-500/50 hover:bg-white/10">
					<span class="text-xs font-mono uppercase tracking-widest text-emerald-400 opacity-70">{word.category}</span>
					<span class="text-2xl font-bold tracking-tight">{word.term}</span>
					<div class="absolute inset-0 -z-10 rounded-2xl bg-emerald-500/0 blur-xl transition-all group-hover:bg-emerald-500/10"></div>
				</button>
			{/each}
		</div>

		<div class="river-row animate-river" style="--duration: {Math.max(appState.filteredWords.length * 15, 200)}s;">
			{#each [...appState.filteredWords, ...appState.filteredWords] as word}
				<button onclick={() => appState.selectWord(word)} class="group relative flex flex-col items-start gap-1 rounded-2xl border border-white/10 bg-white/5 p-6 backdrop-blur-md transition-all hover:scale-105 hover:border-cyan-500/50 hover:bg-white/10">
					<span class="text-xs font-mono uppercase tracking-widest text-purple-400 opacity-70">{word.category}</span>
					<span class="text-2xl font-bold tracking-tight">{word.term}</span>
					<div class="absolute inset-0 -z-10 rounded-2xl bg-purple-500/0 blur-xl transition-all group-hover:bg-purple-500/10"></div>
				</button>
			{/each}
		</div>
	</div>

	{#if appState.isDrawerOpen && appState.activeWord}
		<div class="absolute right-0 top-0 z-50 flex h-full w-full flex-col overflow-y-auto border-l border-white/10 bg-slate-900/95 p-10 shadow-2xl backdrop-blur-3xl sm:w-[500px]">
			
			<button
				onclick={() => appState.closeDrawer()}
				class="mb-8 flex items-center gap-2 self-start text-sm text-slate-400 transition-colors hover:text-white"
			>
				<span class="text-lg">←</span> Back to River
			</button>

			<div class="mb-8">
				<span class="rounded-full border border-cyan-500/30 bg-cyan-500/10 px-3 py-1 text-xs font-mono uppercase text-cyan-400">
					{appState.activeWord.category}
				</span>
				<h2 class="mt-4 text-4xl font-bold tracking-tight text-white">
					{appState.activeWord.term}
				</h2>
			</div>

			<div class="space-y-4 text-base leading-relaxed text-slate-300">
				<p>{appState.activeWord.definition}</p>
			</div>

			{#if appState.activeWord.ripples && appState.activeWord.ripples.length > 0}
				<div class="mt-8 flex flex-wrap items-center gap-2">
					<span class="mr-2 text-sm font-bold uppercase tracking-widest text-slate-500">Related:</span>
					{#each appState.activeWord.ripples as ripple}
						<button
							class="text-sm text-cyan-400 underline decoration-wavy underline-offset-4 transition-colors hover:text-cyan-300"
							onclick={() => {
								appState.closeDrawer();
								appState.searchQuery = ripple.term;
							}}
						>
							{ripple.term}
						</button>
					{/each}
				</div>
			{/if}

			<div class="mt-8 rounded-xl border border-white/10 bg-white/5 p-6">
				<h3 class="mb-4 text-sm font-bold uppercase tracking-widest text-slate-500">Source Papers</h3>

				{#if appState.activeWord.sources && appState.activeWord.sources.length > 0}
					<div class="grid grid-cols-2 gap-3">
						{#each appState.activeWord.sources as source}
							<a
								href={source.url || source.link || '#'}
								target="_blank"
								rel="noopener noreferrer"
								class="group flex flex-col gap-1 rounded-lg border border-white/5 bg-slate-900/50 p-3 transition-colors hover:border-cyan-500/30 hover:bg-slate-800/80"
							>
								<h4 class="text-xs font-bold text-slate-200 line-clamp-2 group-hover:text-cyan-400">
									{source.title}
								</h4>
								<p class="text-[10px] text-slate-400 line-clamp-3">
									{source.summary || 'No summary available.'}
								</p>
							</a>
						{/each}
					</div>
				{:else}
					<p class="text-sm italic text-slate-400">No source papers linked to this term.</p>
				{/if}
			</div>
		</div>
	{/if}
</main>

<style>
	.river-row {
		display: flex;
		width: max-content;
		gap: 2rem;
		padding-left: 2rem;
	}

	@keyframes scroll-river-ltr {
		0% { transform: translateX(-50%); }
		100% { transform: translateX(0); }
	}

	.animate-river { 
		animation: scroll-river-ltr var(--duration, 60s) linear infinite; 
	}
</style>