# Build the hand-authored LaTeX edition of the Big_Agent manual.
#
#   make          -> big_agent_documentation.pdf
#   make clean    -> remove build artefacts, keep the PDF
#   make distclean-> remove the PDF too
#
# latexmk handles the repeated passes the table of contents and the
# cross-references need. Without it, run pdflatex twice.

MAIN    = big_agent_documentation
LATEXMK = latexmk
PDFLATEX = pdflatex

.PHONY: all pdf clean distclean

all: pdf

pdf: $(MAIN).pdf

# version.tex reads app/version.py at build time, so a version bump there must
# also trigger a rebuild.
$(MAIN).pdf: $(MAIN).tex preamble.tex version.tex ../../app/version.py $(wildcard chapters/*.tex)
	@command -v $(LATEXMK) >/dev/null 2>&1 \
		&& $(LATEXMK) -pdf -interaction=nonstopmode -halt-on-error $(MAIN).tex \
		|| ($(PDFLATEX) -interaction=nonstopmode -halt-on-error $(MAIN).tex \
		    && $(PDFLATEX) -interaction=nonstopmode -halt-on-error $(MAIN).tex)

clean:
	-$(LATEXMK) -c $(MAIN).tex 2>/dev/null || true
	-rm -f $(MAIN).aux $(MAIN).log $(MAIN).out $(MAIN).toc \
	       $(MAIN).fls $(MAIN).fdb_latexmk chapters/*.aux

distclean: clean
	-rm -f $(MAIN).pdf
