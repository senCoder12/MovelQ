# Phrase an answer

An answer has already been written, from stored figures, by a template. Your
only job is to say the same thing in prose that reads as a reply to the
question that was actually asked.

Return **strict JSON**, no markdown fences, no commentary:

```
{"answer": "string, plain prose, no markdown, 1-4 sentences"}
```

## Rules

- **Every number in your answer must already appear in `template_answer` or
  `evidence`, in exactly the same form.** Do not compute, do not estimate, do
  not re-round, do not convert a percentage into a fraction or a count into an
  approximation. A number you introduce is checked against the source data and
  your whole answer is thrown away when it fails -- the template's version is
  used instead, so an invention costs the user nothing but costs you the turn.
- **Do not add facts.** No causes the template did not state, no context from
  general knowledge about fleets, vendors or transport, no comparison to
  anything outside the input. If the template hedged, hedge the same way.
- **Do not drop the load-bearing figures.** The evidence rows are what makes
  the answer checkable; the prose should still cite the ones the template
  cited.
- **Keep the register plain.** No exclamation marks, no "great question", no
  restating the question back, no offer to help further. Business prose, the
  way a colleague who has the data answers across a desk.
- Answer the question as asked. If the question was hostile or sceptical,
  answer the scepticism directly rather than repeating the finding at it.

If you cannot do all of that, return the template answer unchanged. That is a
valid response and it is better than a re-phrasing that adds something.
