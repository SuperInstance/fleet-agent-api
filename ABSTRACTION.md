primary_plane: 3
reads_from: [3, 4, 5]
writes_to: [3]
floor: 3
ceiling: 5
compilers: []
reasoning: |
  Fleet-agent-api is an HTTP API operating at Plane 3 (structured IR/JSON).
  It provides typed, verifiable interfaces for fleet communication, accepting natural
  Intent (5), Domain Language (4), or structured IR (3) requests and returning
  structured IR responses. This enables verification, type safety, and protocol
  adherence.

  The API acts as the protocol layer: it validates inputs, enforces types, and ensures
  all fleet communications are in structured, machine-verifiable format. Floor at 3
  means it deals exclusively with structured data, never descending to bytecode
  interpretation or native code.
